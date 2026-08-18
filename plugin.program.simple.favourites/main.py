# Copyright primaeval - but you can use it for free if you can be nice to someone all day :)

import re
import urllib.parse
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from xbmcswift2 import Plugin

from rpc import RPC

plugin = Plugin()
big_list_view = False


def addon_id():
    return xbmcaddon.Addon().getAddonInfo('id')


def log(v):
    xbmc.log(repr(v))


def get_icon_path(icon_name):
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_id(), icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_id(), icon_name)


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]", '', label)
    label = re.sub(r"\[/?COLOR.*?\]", '', label)
    return label


def escape(str):
    str = str.replace("&", "&amp;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    str = str.replace("\"", "&quot;")
    return str


def unescape(str):
    str = str.replace("&lt;", "<")
    str = str.replace("&gt;", ">")
    str = str.replace("&quot;", "\"")
    str = str.replace("&amp;", "&")
    return str


def cleanFolder(path):
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        full = path + '/' + file
        xbmcvfs.delete(full)
    for dir in dirs:
        full = path + '/' + dir
        cleanFolder(full)
    xbmcvfs.rmdir(path)


@plugin.route('/nuke')
def nuke():
    url = plugin.get_setting('url')
    if not url:
        return
    d = xbmcgui.Dialog()
    yes = d.yesno("Replace Everything", "Are you sure?")
    if not yes:
        return
    d.notification("Simple Favourites", "Starting Replacement...")
    replace(url)
    d.notification("Simple Favourites", "Finished Replacement")


@plugin.route('/replace/<url>')
def replace(url):
    if not url:
        return
    src_folders = "special://profile/addon_data/%s/folders/" % (addon_id())
    dst_folders = "special://profile/addon_data/%s/folders.last/" % (addon_id())
    cleanFolder(dst_folders)
    success = xbmcvfs.rename(src_folders, dst_folders)
    dst = 'special://profile/addon_data/%s/folders.zip' % (addon_id())
    success = xbmcvfs.copy(url, dst)
    path = xbmcvfs.translatePath('special://profile/addon_data/%s/folders.zip' % (addon_id()))
    f = open(path, 'rb')
    zf = zipfile.ZipFile(f)
    addon_data = "special://profile/addon_data/%s/" % (addon_id())
    zf.extractall(xbmcvfs.translatePath(addon_data))


@plugin.route('/play/<url>')
def play(url):
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    xbmc.executebuiltin('PlayMedia("%s")' % url)


@plugin.route('/execute/<url>')
def execute(url):
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    xbmc.executebuiltin(url)


@plugin.route('/add_favourite/<favourites_file>/<name>/<url>/<thumbnail>/<fanart>')
def add_favourite(favourites_file, name, url, thumbnail, fanart):
    xbmcvfs.mkdirs("special://profile/addon_data/%s/folders/" % (addon_id()))
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    f.close()
    if not data:
        data = '<favourites>\n</favourites>'
    fav = '    <favourite name="%s" thumb="%s" fanart="%s">%s</favourite>\n</favourites>' % (
        name, thumbnail, fanart, url)
    data = data.replace('</favourites>', fav)
    f = xbmcvfs.File(favourites_file, "wb")
    f.write(data)
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/move_favourite/<favourites_file>/<name>/<url>')
def move_favourite(favourites_file, name, url):
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    favourites = re.findall("<favourite.*?</favourite>", data)
    if len(favourites) < 2:
        return
    favs = []
    for fav in favourites:
        fav_url = ''
        match = re.search('>(.*?)<', fav)
        if match:
            fav_url = match.group(1)
        label = ''
        match = re.search('name="(.*?)"', fav)
        if match:
            label = match.group(1)
        thumbnail = get_icon_path('unknown')
        match = re.search('thumb="(.*?)"', fav)
        if match:
            thumbnail = match.group(1)
        fanart = 'none'
        match = re.search('fanart="(.*?)"', fav)
        if match:
            fanart = match.group(1)
        if not fanart.strip():
            fanart = 'none'
        if url == fav_url:
            fav_thumbnail = thumbnail
            fav_fanart = fanart
            continue
        favs.append((label, thumbnail, fanart, fav_url))

    labels = [x[0] for x in favs]
    d = xbmcgui.Dialog()
    where = d.select("Move [ %s ] After" % name, labels)
    if where > -1 and where < len(favs):
        favs.insert(where + 1, (name, fav_thumbnail, fav_fanart, url))

    f = xbmcvfs.File(favourites_file, "wb")
    f.write("<favourites>\n")
    for fav in favs:
        str = '    <favourite name="%s" thumb="%s" fanart="%s">%s</favourite>\n' % fav
        f.write(str)
    f.write("</favourites>")
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/move_favourite_to_folder/<favourites_file>/<name>/<url>/<thumbnail>/<fanart>')
def move_favourite_to_folder(favourites_file, name, url, thumbnail, fanart):
    d = xbmcgui.Dialog()
    top_folder = 'special://profile/addon_data/%s/folders/' % addon_id()
    # TODO handle formatted folder names
    where = d.browse(0, 'Choose Folder', 'files', '', False, True, top_folder)
    if not where:
        return
    if not where.startswith(top_folder):
        d.notification("Error", "Please keep to the folders path")
        return
    remove_favourite(favourites_file, name, url)
    favourites_file = "%sfavourites.xml" % where
    add_favourite(favourites_file, name, url, thumbnail, fanart)


@plugin.route('/remove_favourite/<favourites_file>/<name>/<url>')
def remove_favourite(favourites_file, name, url):
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    f.close()
    data = re.sub('.*<favourite name="%s".*?>%s</favourite>.*\n' % (re.escape(name), re.escape(url)), '', data)
    f = xbmcvfs.File(favourites_file, "wb")
    f.write(data)
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/rename_favourite/<favourites_file>/<name>/<fav>')
def rename_favourite(favourites_file, name, fav):
    d = xbmcgui.Dialog()
    dialog_name = unescape(name)
    new_name = d.input("New Name for: %s" % dialog_name, dialog_name)
    if not new_name:
        return
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    f.close()
    new_fav = fav.replace('name="%s"' % name, 'name="%s"' % escape(new_name))
    data = data.replace(fav, new_fav)
    f = xbmcvfs.File(favourites_file, "wb")
    f.write(data)
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_favourite_thumbnail/<favourites_file>/<thumbnail>/<fav>')
def change_favourite_thumbnail(favourites_file, thumbnail, fav):
    d = xbmcgui.Dialog()
    new_thumbnail = d.browse(2, 'Choose Image', 'files')
    if not new_thumbnail:
        return
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    f.close()
    new_fav = fav.replace('thumb="%s"' % thumbnail, 'thumb="%s"' % escape(new_thumbnail))
    data = data.replace(fav, new_fav)
    f = xbmcvfs.File(favourites_file, "wb")
    f.write(data)
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_favourite_fanart/<favourites_file>/<fanart>/<fav>')
def change_favourite_fanart(favourites_file, fanart, fav):
    d = xbmcgui.Dialog()
    new_fanart = d.browse(2, 'Choose Image', 'files')
    if not new_fanart:
        return
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    f.close()
    new_fav = fav.replace('fanart="%s"' % fanart, 'fanart="%s"' % escape(new_fanart))
    data = data.replace(fav, new_fav)
    f = xbmcvfs.File(favourites_file, "wb")
    f.write(data)
    f.close()
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/favourites/<folder_path>')
def favourites(folder_path):
    items = []
    favourites_file = "%sfavourites.xml" % folder_path
    f = xbmcvfs.File(favourites_file, "rb")
    data = f.read()
    favourites = re.findall("<favourite.*?</favourite>", data)
    for fav in favourites:
        url = ''
        match = re.search('>(.*?)<', fav)
        if match:
            url = match.group(1)
        label = ''
        match = re.search('name="(.*?)"', fav)
        if match:
            label = match.group(1)
        thumbnail = get_icon_path('unknown')
        match = re.search('thumb="(.*?)"', fav)
        if match:
            thumbnail = match.group(1)
        fanart = 'none'
        match = re.search('fanart="(.*?)"', fav)
        if match:
            fanart = match.group(1)
        if not fanart.strip():
            fanart = 'none'
        if url:
            context_items = []
            if plugin.get_setting('edit') == 'true':
                if plugin.get_setting('add') == 'false':
                    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Menu',
                                          'ActivateWindow(10001,"%s")' % (plugin.url_for('add', path=folder_path))))
                if plugin.get_setting('sort') == 'false':
                    context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Move', 'RunPlugin(%s)' % (
                        plugin.url_for(move_favourite, favourites_file=favourites_file, name=label, url=url))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Move to Folder', 'RunPlugin(%s)' % (
                    plugin.url_for(move_favourite_to_folder, favourites_file=favourites_file, name=label, url=url,
                                   thumbnail=thumbnail, fanart=fanart))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'RunPlugin(%s)' % (
                    plugin.url_for(remove_favourite, favourites_file=favourites_file, name=label, url=url))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Rename', 'RunPlugin(%s)' % (
                    plugin.url_for(rename_favourite, favourites_file=favourites_file, name=label, fav=fav))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Thumbnail', 'RunPlugin(%s)' % (
                    plugin.url_for(change_favourite_thumbnail, favourites_file=favourites_file, thumbnail=thumbnail,
                                   fav=fav))))
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Fanart', 'RunPlugin(%s)' % (
                    plugin.url_for(change_favourite_fanart, favourites_file=favourites_file, fanart=fanart, fav=fav))))
            item = {'label': unescape(label), 'path': plugin.url_for('execute', url=unescape(url)),
                    'thumbnail': unescape(thumbnail), 'context_menu': context_items, }
            if fanart != 'none':
                item['properties'] = {'Fanart_Image': fanart}
            items.append(item)
    return items


@plugin.route('/add_favourites/<path>')
def add_favourites(path):
    items = []
    kodi_favourites = "special://profile/favourites.xml"
    output_file = "%sfavourites.xml" % path
    f = xbmcvfs.File(kodi_favourites, "rb")
    data = f.read()
    favourites = re.findall("<favourite.*?</favourite>", data)
    for fav in favourites:
        url = ''
        match = re.search('>(.*?)<', fav)
        if match:
            url = match.group(1)
        label = ''
        match = re.search('name="(.*?)"', fav)
        if match:
            label = match.group(1)
        thumbnail = get_icon_path('unknown')
        match = re.search('thumb="(.*?)"', fav)
        if match:
            thumbnail = match.group(1)
        fanart = 'none'
        match = re.search('fanart="(.*?)"', fav)
        if match:
            fanart = match.group(1)
        if not fanart.strip():
            fanart = 'none'
        if url:
            context_items = []
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'RunPlugin(%s)' % (
                plugin.url_for(add_favourite, favourites_file=output_file, name=label, url=url, thumbnail=thumbnail,
                               fanart=fanart))))
            item = {'label': unescape(label), 'path': plugin.url_for('execute', url=unescape(url)),
                    'thumbnail': unescape(thumbnail), 'context_menu': context_items, }
            if fanart != 'none':
                item['properties'] = {'Fanart_Image': fanart}
            items.append(item)
    return items


@plugin.route('/add_folder/<path>')
def add_folder(path):
    d = xbmcgui.Dialog()
    folder_name = d.input("New Folder")
    if not folder_name:
        return
    quoted_folder_name = urllib.parse.quote(folder_name, safe='')
    path = "%s%s/" % (path, quoted_folder_name)
    xbmcvfs.mkdirs(path)
    folder_icon = get_icon_path('folder')
    icon_file = path + "icon.txt"
    xbmcvfs.File(icon_file, "wb").write(folder_icon)
    fanart_file = path + "fanart.txt"
    xbmcvfs.File(fanart_file, "wb").write('none')


def remove_files(path):
    dirs, files = xbmcvfs.listdir(path)
    for d in dirs:
        remove_files("%s%s/" % (path, d))
    for f in files:
        xbmcvfs.delete("%s%s" % (path, f))
    xbmcvfs.rmdir(path)


@plugin.route('/remove_folder/<path>')
def remove_folder(path):
    d = xbmcgui.Dialog()
    yes = d.yesno("Remove Folder", "Are you sure?")
    if not yes:
        return
    remove_files(path)
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/rename_folder/<path>/<name>')
def rename_folder(path, name):
    d = xbmcgui.Dialog()
    unquoted_name = urllib.parse.unquote(name)
    new_name = d.input("New Name for: %s" % unquoted_name, unquoted_name)
    if not new_name:
        return
    quoted_new_name = urllib.parse.quote(new_name, safe='')
    old_folder = "%s%s/" % (path, name)
    new_folder = "%s%s/" % (path, quoted_new_name)
    xbmcvfs.rename(old_folder, new_folder)
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_folder_thumbnail/<path>')
def change_folder_thumbnail(path):
    d = xbmcgui.Dialog()
    new_thumbnail = d.browse(2, 'Choose Image', 'files')
    if not new_thumbnail:
        return
    icon_file = "%sicon.txt" % path
    xbmcvfs.File(icon_file, "wb").write(new_thumbnail)
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_folder_fanart/<path>')
def change_folder_fanart(path):
    d = xbmcgui.Dialog()
    new_fanart = d.browse(2, 'Choose Image', 'files')
    if not new_fanart:
        return
    fanart_file = "%sfanart.txt" % path
    xbmcvfs.File(fanart_file, "wb").write(new_fanart)
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_folder_colour/<path>')
def change_folder_colour(path):
    d = xbmcgui.Dialog()
    colours = ["[COLOR fff0f8ff]aliceblue[/COLOR]", "[COLOR fffaebd7]antiquewhite[/COLOR]",
               "[COLOR ff00ffff]aqua[/COLOR]", "[COLOR ff7fffd4]aquamarine[/COLOR]", "[COLOR fff0ffff]azure[/COLOR]",
               "[COLOR fff5f5dc]beige[/COLOR]", "[COLOR ffffe4c4]bisque[/COLOR]", "[COLOR ff606060]black[/COLOR]",
               "[COLOR ffffebcd]blanchedalmond[/COLOR]", "[COLOR ff0000ff]blue[/COLOR]",
               "[COLOR ff8a2be2]blueviolet[/COLOR]", "[COLOR ffa52a2a]brown[/COLOR]",
               "[COLOR ffdeb887]burlywood[/COLOR]", "[COLOR ff5f9ea0]cadetblue[/COLOR]",
               "[COLOR ff7fff00]chartreuse[/COLOR]", "[COLOR ffd2691e]chocolate[/COLOR]",
               "[COLOR ffff7f50]coral[/COLOR]", "[COLOR ff6495ed]cornflowerblue[/COLOR]",
               "[COLOR fffff8dc]cornsilk[/COLOR]", "[COLOR ffdc143c]crimson[/COLOR]", "[COLOR ff00ffff]cyan[/COLOR]",
               "[COLOR ff00008b]darkblue[/COLOR]", "[COLOR ff008b8b]darkcyan[/COLOR]",
               "[COLOR ffb8860b]darkgoldenrod[/COLOR]", "[COLOR ffa9a9a9]darkgray[/COLOR]",
               "[COLOR ff006400]darkgreen[/COLOR]", "[COLOR ffa9a9a9]darkgrey[/COLOR]",
               "[COLOR ffbdb76b]darkkhaki[/COLOR]", "[COLOR ff8b008b]darkmagenta[/COLOR]",
               "[COLOR ff556b2f]darkolivegreen[/COLOR]", "[COLOR ffff8c00]darkorange[/COLOR]",
               "[COLOR ff9932cc]darkorchid[/COLOR]", "[COLOR ff8b0000]darkred[/COLOR]",
               "[COLOR ffe9967a]darksalmon[/COLOR]", "[COLOR ff8fbc8f]darkseagreen[/COLOR]",
               "[COLOR ff483d8b]darkslateblue[/COLOR]", "[COLOR ff2f4f4f]darkslategray[/COLOR]",
               "[COLOR ff2f4f4f]darkslategrey[/COLOR]", "[COLOR ff00ced1]darkturquoise[/COLOR]",
               "[COLOR ff9400d3]darkviolet[/COLOR]", "[COLOR ffff1493]deeppink[/COLOR]",
               "[COLOR ff00bfff]deepskyblue[/COLOR]", "[COLOR ff696969]dimgray[/COLOR]",
               "[COLOR ff696969]dimgrey[/COLOR]", "[COLOR ff1e90ff]dodgerblue[/COLOR]",
               "[COLOR ffb22222]firebrick[/COLOR]", "[COLOR fffffaf0]floralwhite[/COLOR]",
               "[COLOR ff228b22]forestgreen[/COLOR]", "[COLOR ffff00ff]fuchsia[/COLOR]",
               "[COLOR ffdcdcdc]gainsboro[/COLOR]", "[COLOR fff8f8ff]ghostwhite[/COLOR]",
               "[COLOR ffffd700]gold[/COLOR]", "[COLOR ffdaa520]goldenrod[/COLOR]", "[COLOR ff808080]gray[/COLOR]",
               "[COLOR ff008000]green[/COLOR]", "[COLOR ffadff2f]greenyellow[/COLOR]", "[COLOR ff808080]grey[/COLOR]",
               "[COLOR fff0fff0]honeydew[/COLOR]", "[COLOR ffff69b4]hotpink[/COLOR]",
               "[COLOR ffcd5c5c]indianred[/COLOR]", "[COLOR ff4b0082]indigo[/COLOR]", "[COLOR fffffff0]ivory[/COLOR]",
               "[COLOR fff0e68c]khaki[/COLOR]", "[COLOR ffe6e6fa]lavender[/COLOR]",
               "[COLOR fffff0f5]lavenderblush[/COLOR]", "[COLOR ff7cfc00]lawngreen[/COLOR]",
               "[COLOR fffffacd]lemonchiffon[/COLOR]", "[COLOR ffadd8e6]lightblue[/COLOR]",
               "[COLOR fff08080]lightcoral[/COLOR]", "[COLOR ffe0ffff]lightcyan[/COLOR]",
               "[COLOR fffafad2]lightgoldenrodyellow[/COLOR]", "[COLOR ffd3d3d3]lightgray[/COLOR]",
               "[COLOR ff90ee90]lightgreen[/COLOR]", "[COLOR ffd3d3d3]lightgrey[/COLOR]",
               "[COLOR ffffb6c1]lightpink[/COLOR]", "[COLOR ffffa07a]lightsalmon[/COLOR]",
               "[COLOR ff20b2aa]lightseagreen[/COLOR]", "[COLOR ff87cefa]lightskyblue[/COLOR]",
               "[COLOR ff778899]lightslategray[/COLOR]", "[COLOR ff778899]lightslategrey[/COLOR]",
               "[COLOR ffb0c4de]lightsteelblue[/COLOR]", "[COLOR ffffffe0]lightyellow[/COLOR]",
               "[COLOR ff00ff00]lime[/COLOR]", "[COLOR ff32cd32]limegreen[/COLOR]", "[COLOR fffaf0e6]linen[/COLOR]",
               "[COLOR ffff00ff]magenta[/COLOR]", "[COLOR ff800000]maroon[/COLOR]",
               "[COLOR ff66cdaa]mediumaquamarine[/COLOR]", "[COLOR ff0000cd]mediumblue[/COLOR]",
               "[COLOR ffba55d3]mediumorchid[/COLOR]", "[COLOR ff9370db]mediumpurple[/COLOR]",
               "[COLOR ff3cb371]mediumseagreen[/COLOR]", "[COLOR ff7b68ee]mediumslateblue[/COLOR]",
               "[COLOR ff00fa9a]mediumspringgreen[/COLOR]", "[COLOR ff48d1cc]mediumturquoise[/COLOR]",
               "[COLOR ffc71585]mediumvioletred[/COLOR]", "[COLOR ff191970]midnightblue[/COLOR]",
               "[COLOR fff5fffa]mintcream[/COLOR]", "[COLOR ffffe4e1]mistyrose[/COLOR]",
               "[COLOR ffffe4b5]moccasin[/COLOR]", "[COLOR ffffdead]navajowhite[/COLOR]",
               "[COLOR ff000080]navy[/COLOR]", "[COLOR 00000000]none[/COLOR]", "[COLOR fffdf5e6]oldlace[/COLOR]",
               "[COLOR ff808000]olive[/COLOR]", "[COLOR ff6b8e23]olivedrab[/COLOR]", "[COLOR ffffa500]orange[/COLOR]",
               "[COLOR ffff4500]orangered[/COLOR]", "[COLOR ffda70d6]orchid[/COLOR]",
               "[COLOR ffeee8aa]palegoldenrod[/COLOR]", "[COLOR ff98fb98]palegreen[/COLOR]",
               "[COLOR ffafeeee]paleturquoise[/COLOR]", "[COLOR ffdb7093]palevioletred[/COLOR]",
               "[COLOR ffffefd5]papayawhip[/COLOR]", "[COLOR ffffdab9]peachpuff[/COLOR]",
               "[COLOR ffcd853f]peru[/COLOR]", "[COLOR ffffc0cb]pink[/COLOR]", "[COLOR ffdda0dd]plum[/COLOR]",
               "[COLOR ffb0e0e6]powderblue[/COLOR]", "[COLOR ff800080]purple[/COLOR]", "[COLOR ffff0000]red[/COLOR]",
               "[COLOR ffbc8f8f]rosybrown[/COLOR]", "[COLOR ff4169e1]royalblue[/COLOR]",
               "[COLOR ff8b4513]saddlebrown[/COLOR]", "[COLOR fffa8072]salmon[/COLOR]",
               "[COLOR fff4a460]sandybrown[/COLOR]", "[COLOR ff2e8b57]seagreen[/COLOR]",
               "[COLOR fffff5ee]seashell[/COLOR]", "[COLOR ffa0522d]sienna[/COLOR]", "[COLOR ffc0c0c0]silver[/COLOR]",
               "[COLOR ff87ceeb]skyblue[/COLOR]", "[COLOR ff6a5acd]slateblue[/COLOR]",
               "[COLOR ff708090]slategray[/COLOR]", "[COLOR ff708090]slategrey[/COLOR]", "[COLOR fffffafa]snow[/COLOR]",
               "[COLOR ff00ff7f]springgreen[/COLOR]", "[COLOR ff4682b4]steelblue[/COLOR]",
               "[COLOR ffd2b48c]tan[/COLOR]", "[COLOR ff008080]teal[/COLOR]", "[COLOR ffd8bfd8]thistle[/COLOR]",
               "[COLOR ffff6347]tomato[/COLOR]", "[COLOR 00000000]transparent[/COLOR]",
               "[COLOR ff40e0d0]turquoise[/COLOR]", "[COLOR ffee82ee]violet[/COLOR]", "[COLOR fff5deb3]wheat[/COLOR]",
               "[COLOR ffffffff]white[/COLOR]", "[COLOR fff5f5f5]whitesmoke[/COLOR]", "[COLOR ffffff00]yellow[/COLOR]",
               "[COLOR ff9acd32]yellowgreen[/COLOR]"]
    index = d.select("Choose Colour", colours)
    if index == -1:
        return
    colour = colours[index]
    colour = colour[7:15]
    colour_file = "%scolour.txt" % path
    xbmcvfs.File(colour_file, "wb").write(colour)
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/set_password/<path>')
def set_password(path):
    d = xbmcgui.Dialog()
    password_file = "%spassword.txt" % path
    f = xbmcvfs.File(password_file, 'rb')
    password = f.read()
    f.close()
    if password:
        input = d.input('Current Password')
        if input != password:
            return
    password = d.input('New Password')
    xbmcvfs.File(password_file, "wb").write(password)


@plugin.route('/add_addons_folder/<favourites_file>/<media>/<path>')
def add_addons_folder(favourites_file, media, path):
    try:
        response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail", "fanart"])
    except:
        return
    files = response["files"]
    dir_items = []
    file_items = []
    for f in files:
        label = remove_formatting(f['label'])
        url = f['file']
        thumbnail = f['thumbnail']
        if not thumbnail:
            thumbnail = get_icon_path('unknown')
        fanart = f.get('fanart', 'none')
        if not fanart.strip():
            fanart = 'none'
        context_items = []
        if f['filetype'] == 'directory':
            if media == "video":
                window = "videos"
            elif media in ["music", "audio"]:
                window = "music"
            elif media in ["executable", "programs"]:
                media = "programs"
                window = "programs"
            elif media in ["image", "pictures"]:
                media = "pictures"
                window = "pictures"
            else:
                media = "programs"
                window = "programs"
            play_url = escape('ActivateWindow(%s,"%s",return)' % (window, url))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'RunPlugin(%s)' % (
                plugin.url_for(add_favourite, favourites_file=favourites_file, name=label.encode("utf8"), url=play_url,
                               thumbnail=thumbnail, fanart=fanart))))
            item = {'label': "[B]%s[/B]" % label,
                    'path': plugin.url_for('add_addons_folder', favourites_file=favourites_file, media=media, path=url),
                    'thumbnail': f['thumbnail'], 'context_menu': context_items, }
            if fanart != 'none':
                item['properties'] = {'Fanart_Image': fanart}
            dir_items.append(item)
        else:
            play_url = escape('PlayMedia("%s")' % url)
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'RunPlugin(%s)' % (
                plugin.url_for(add_favourite, favourites_file=favourites_file, name=label.encode("utf8"), url=play_url,
                               thumbnail=thumbnail, fanart=fanart))))
            item = {'label': "%s" % label, 'path': plugin.url_for('play', url=url), 'thumbnail': f['thumbnail'],
                    'context_menu': context_items, }
            if fanart != 'none':
                item['properties'] = {'Fanart_Image': fanart}
            file_items.append(item)
    return sorted(dir_items, key=lambda x: x["label"].lower()) + sorted(file_items, key=lambda x: x["label"].lower())


@plugin.route('/add_addons/<favourites_file>/<media>')
def add_addons(favourites_file, media):
    type = "xbmc.addon.%s" % media

    response = RPC.addons.get_addons(type=type, properties=["name", "thumbnail", "fanart"])
    if "addons" not in response:
        return

    addons = response["addons"]

    items = []

    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    for addon in addons:
        label = addon['name']
        id = addon['addonid']
        thumbnail = addon['thumbnail']
        if not thumbnail:
            thumbnail = get_icon_path('unknown')
        fanart = addon.get('fanart', 'none')
        if not fanart.strip():
            fanart = 'none'
        path = "plugin://%s" % id
        context_items = []
        fancy_label = "[B]%s[/B]" % label
        if media == "video":
            window = "videos"
        elif media in ["music", "audio"]:
            window = "music"
        elif media in ["executable", "programs"]:
            media = "programs"
            window = "programs"
        elif media in ["image", "pictures"]:
            media = "pictures"
            window = "pictures"
        else:
            media = "programs"
            window = "programs"
        if id.startswith("script"):
            play_url = escape('RunScript("%s")' % (id))
        else:
            play_url = escape('ActivateWindow(%s,"%s",return)' % (window, path))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'RunPlugin(%s)' % (
            plugin.url_for(add_favourite, favourites_file=favourites_file, name=label.encode("utf8"), url=play_url,
                           thumbnail=thumbnail, fanart=fanart))))
        item = {'label': fancy_label,
                'path': plugin.url_for('add_addons_folder', favourites_file=favourites_file, media=media, path=path),
                'thumbnail': thumbnail, 'context_menu': context_items, }
        if fanart != 'none':
            item['properties'] = {'Fanart_Image': fanart}
        items.append(item)
    return items


@plugin.route('/add/<path>')
def add(path):
    favourites_file = "%sfavourites.xml" % path
    items = []

    for media in ["video", "music"]:
        label = media
        lib_path = "library://%s" % media
        thumbnail = get_icon_path(media)
        items.append({'label': "[B]%s Library[/B]" % media.title(),
                      'path': plugin.url_for('add_addons_folder', favourites_file=favourites_file, media=media,
                                             path=lib_path), 'thumbnail': thumbnail, })

    for media in ["video", "audio", "executable", "image"]:
        label = media
        thumbnail = get_icon_path(media)
        items.append({'label': "[B]%s Addons[/B]" % media.title(),
                      'path': plugin.url_for('add_addons', favourites_file=favourites_file, media=media),
                      'thumbnail': thumbnail, })

    items.append({'label': "[B]Favourites[/B]", 'path': plugin.url_for('add_favourites', path=path),
                  'thumbnail': get_icon_path('favourites'), })

    items.append({'label': "New Folder", 'path': plugin.url_for('add_folder', path=path),
                  'thumbnail': get_icon_path('settings'), })
    return items


@plugin.route('/')
def index(silent=False):
    folder_path = "special://profile/addon_data/%s/folders/" % (addon_id())
    return index_of(folder_path, silent)


@plugin.route('/index_of/<path>')
def index_of(path=None, silent=False):
    items = []
    if path:
        password_file = "%spassword.txt" % path
        password = xbmcvfs.File(password_file, "rb").read()
        if password:
            input = xbmcgui.Dialog().input('Password:')
            if input != password:
                return

    folders, files = xbmcvfs.listdir(path)
    for folder in sorted(folders, key=lambda x: x.lower()):
        folder_path = "%s%s/" % (path, folder)
        thumbnail_file = "%sicon.txt" % folder_path
        thumbnail = xbmcvfs.File(thumbnail_file, "rb").read()
        fanart_file = "%sfanart.txt" % folder_path
        fanart = xbmcvfs.File(fanart_file, "rb").read()
        colour_file = "%scolour.txt" % folder_path
        colour = xbmcvfs.File(colour_file, "rb").read()
        context_items = []
        if plugin.get_setting('edit') == 'true':
            if plugin.get_setting('add') == 'false':
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add Menu',
                                      'ActivateWindow(10001,"%s")' % (plugin.url_for('add', path=path))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove',
                                  'RunPlugin(%s)' % (plugin.url_for(remove_folder, path=folder_path))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Rename',
                                  'RunPlugin(%s)' % (plugin.url_for(rename_folder, path=path, name=folder))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Thumbnail',
                                  'RunPlugin(%s)' % (plugin.url_for(change_folder_thumbnail, path=folder_path))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Fanart',
                                  'RunPlugin(%s)' % (plugin.url_for(change_folder_fanart, path=folder_path))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Colour',
                                  'RunPlugin(%s)' % (plugin.url_for(change_folder_colour, path=folder_path))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Set Password',
                                  'RunPlugin(%s)' % (plugin.url_for(set_password, path=folder_path))))
        label = urllib.parse.unquote(folder)
        if colour:
            label = "[COLOR %s]%s[/COLOR]" % (colour, remove_formatting(label))
        item = {'label': label, 'path': plugin.url_for('index_of', path=folder_path), 'thumbnail': thumbnail,
                'context_menu': context_items, }
        if fanart.strip() and fanart != 'none':
            item['properties'] = {'Fanart_Image': fanart}
        items.append(item)

    if plugin.get_setting('sort') == 'true':
        items = items + sorted(favourites(path), key=lambda x: x["label"].lower())
    else:
        items = items + favourites(path)

    if not items or (plugin.get_setting('add') == 'true'):
        items.append(
            {'label': "Add", 'path': plugin.url_for('add', path=path), 'thumbnail': get_icon_path('settings'), })
    if not silent:
        view = plugin.get_setting('view.type')
        if view != "default":
            plugin.set_content(view)
    return items


if __name__ == '__main__':

    ADDON = xbmcaddon.Addon()
    version = ADDON.getAddonInfo('version')
    if ADDON.getSetting('version') != version:
        ADDON.setSetting('version', version)

    plugin.run()
