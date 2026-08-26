# -*- coding: utf-8 -*-
from vavoo.utils import *

CATALOG_URL = "https://vavoo.to/mediahubmx-catalog.json"
CLIENT_VERSION = "3.1.0"

def _catalog_headers(signature):
	if not signature:
		raise RuntimeError("Keine MediaHubMX-Signatur erhalten")
	return {
		"user-agent": "MediaHubMX/2",
		"content-type": "application/json; charset=utf-8",
		"accept-encoding": "gzip",
		"mediahubmx-signature": signature,
	}

def _catalog_request(signature, group=None, cursor=None):
	filters = {"group": group} if group else {}
	payload = {
		"language": "de",
		"region": "AT",
		"catalogId": "iptv",
		"id": "iptv",
		"adult": False,
		"search": "",
		"sort": "",
		"filter": filters,
		"cursor": cursor,
		"clientVersion": CLIENT_VERSION,
	}
	return request_json(
		"POST",
		CATALOG_URL,
		json=payload,
		headers=_catalog_headers(signature),
		timeout=15,
		retries=1,
	)

def _groups_from_catalog(catalog):
	features = catalog.get("features", {})
	filters = features.get("filter", []) if isinstance(features, dict) else []
	if isinstance(filters, dict):
		filters = filters.values()
	for feature in filters:
		if not isinstance(feature, dict) or feature.get("id") != "group":
			continue
		values = feature.get("values", [])
		if isinstance(values, dict):
			values = values.keys()
		groups = {value.get("name") if isinstance(value, dict) else value for value in values}
		groups = {group for group in groups if group}
		if groups:
			return sorted(groups, key=str.casefold)
	return sorted({
		item.get("group") for item in catalog.get("items", [])
		if isinstance(item, dict) and item.get("group")
	}, key=str.casefold)

def vavoo_groups(signature=None):
	log("Getting VAVOO groups and catalog hash")
	signature = signature or getAuthSignature()
	catalog = _catalog_request(signature)
	groups = _groups_from_catalog(catalog)
	# Some responses expose groups only on later catalog pages.
	seen_cursors = set()
	cursor = catalog.get("nextCursor")
	while not groups and cursor is not None and cursor not in seen_cursors:
		seen_cursors.add(cursor)
		page = _catalog_request(signature, cursor=cursor)
		groups = _groups_from_catalog(page)
		cursor = page.get("nextCursor")
	catalog_hash = md5(json.dumps(
		catalog,
		ensure_ascii=False,
		sort_keys=True,
		separators=(",", ":"),
	).encode("utf-8")).hexdigest()
	return groups, catalog_hash

def choose(signature=None):
	signature = signature or getAuthSignature()
	groups, _ = vavoo_groups(signature)
	cacheOk, selected_groups = get_cache("groups")
	preselect = []
	if cacheOk:
		preselect = [
			groups.index(group) for group in selected_groups
			if group in groups
		]
	indices = selectDialog(groups, "Choose VAVOO Groups", True, preselect)
	# Kodi returns None when the dialog is cancelled, but [] when the
	# dialog is confirmed without any selected group.
	if indices is None:
		return selected_groups if cacheOk else []
	selected_groups = [groups[index] for index in indices if 0 <= index < len(groups)]
	set_cache("groups", selected_groups)
	return selected_groups

def new_vav_channels(group=None, signature=None):
	signature = signature or getAuthSignature()
	items = []
	cursor = None
	seen_cursors = set()
	while not monitor.abortRequested():
		catalog = _catalog_request(signature, group=group, cursor=cursor)
		for item in catalog.get("items", []):
			name = item.get("name")
			url = item.get("url")
			item_group = item.get("group")
			if name and url and item_group:
				items.append({"url": url, "name": name, "group": item_group})
		next_cursor = catalog.get("nextCursor")
		if next_cursor is None or next_cursor in seen_cursors:
			break
		seen_cursors.add(next_cursor)
		cursor = next_cursor
	return items

def get_vav_channels(groups=False):
	signature = getAuthSignature()
	if groups is False:
		cacheOk, groups = get_cache("groups")
	if not groups:
		groups = choose(signature)
	if not groups:
		return {}

	cacheOk, channel_cache = get_cache("vav_channels")
	_, new_hash = vavoo_groups(signature)
	if (
		cacheOk
		and isinstance(channel_cache, dict)
		and channel_cache.get("hash") == new_hash
	):
		channels = channel_cache.get("channels", [])
	else:
		log("Getting new VAVOO Channels")
		channels = new_vav_channels(signature=signature)
		set_cache("vav_channels", {"channels": channels, "hash": new_hash})

	vav_channels = {}
	for item in channels:
		if item["group"] not in groups:
			continue
		name = filterout(item["name"])
		if name not in vav_channels:
			vav_channels[name] = []
		if item["url"] not in vav_channels[name]:
			vav_channels[name].append(item["url"])
	return vav_channels
