#
#       Copyright (C) 2016-
#       Sean Poyser (seanpoyser@gmail.com)
#       Portions Copyright (c) 2020 John Moore
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
import sys

import xbmc
import xbmcgui

import main


def getPrefix():
    try:
        return 'Container(%d).' % int(xbmc.getInfoLabel('System.CurrentControlId'))
    except:
        return ''


def add_to_directory(items):
    path, label, thumb, fanart = getCurrentParams()
    if len(items) > 0:
        select = xbmcgui.Dialog().select("Wybór folderu", [x.get("label") for x in items[:-1]])
        if select > -1:
            # selected_path = items[select]['path']
            selected_name = items[select]['label']
            favourites_file = 'special://profile/addon_data/plugin.program.simple.favourites/folders/%s/favourites.xml' % selected_name
            name = label
            url = 'ActivateWindow(videos,&quot;%s&quot;,return)' % path
            main.add_favourite(favourites_file, name, url, thumb, fanart)
        else:
            sys.exit()
    else:
        sys.exit()


def getCurrentParams():
    prefix = getPrefix()

    # window = xbmcgui.getCurrentWindowId()
    # folder = xbmc.getInfoLabel('Container.FolderPath')
    path = xbmc.getInfoLabel('%sListItem.FolderPath' % prefix)
    label = xbmc.getInfoLabel('%sListItem.Label' % prefix)
    # filename = xbmc.getInfoLabel('%sListItem.FilenameAndPath' % prefix)
    # thumb = xbmc.getInfoLabel('%sListItem.Thumb' % prefix)
    # icon = xbmc.getInfoLabel('%sListItem.ActualIcon' % prefix)
    thumb = xbmc.getInfoLabel('%sListItem.Art(thumb)' % prefix)
    # playable = xbmc.getInfoLabel('%sListItem.Property(IsPlayable)' % prefix).lower() == 'true'
    # fanart  = xbmc.getInfoLabel('%sListItem.Property(Fanart_Image)' % prefix)
    fanart = xbmc.getInfoLabel('%sListItem.Art(fanart)' % prefix)
    # isFolder = xbmc.getCondVisibility('%sListItem.IsFolder' % prefix) == 1
    # hasVideo = xbmc.getCondVisibility('Player.HasVideo') == 1
    # picture = xbmc.getInfoLabel('%sListItem.PicturePath' % prefix)
    return path, label, thumb, fanart


try:
    add_to_directory(main.index(silent=True))
except Exception as e:
    pass
