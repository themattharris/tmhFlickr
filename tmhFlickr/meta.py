import json
import os
import pyexiv2
from .utils import say, strip_extension, emit, epoch_to_date_str, decimal_to_dms_fractions

LICENSES = {
  0: "All Rights Reserved",
  1: "Attribution-NonCommercial-ShareAlike License",
  2: "Attribution-NonCommercial License",
  3: "Attribution-NonCommercial-NoDerivs License",
  4: "Attribution License",
  5: "Attribution-ShareAlike License",
  6: "Attribution-NoDerivs License",
  7: "No known copyright restrictions",
  8: "United States Government Work",
  9: "Public Domain Dedication (CC0)",
  10: "Public Domain Mark"
}

# namespace needs to be registered to ensure we can parse the embedded tags
pyexiv2.xmp.register_namespace('http://www.apple.com/apple-fi/', 'apple-fi')

def inspect_embedded(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
  print_embedded(metadata)

def print_embedded(metadata):
  keys = metadata.xmp_keys + metadata.exif_keys + metadata.iptc_keys
  for key in keys:
    try:
      say('{}: {}'.format(key, metadata[key].raw_value))
    except UnicodeDecodeError as e:
      print('{}: {}'.format(key, 'UnicodeDecodeError'))

def inspect_cached(filename):
  meta_json = strip_extension(filename) + ".json"
  meta = read_cached(meta_json)
  if meta == False:
    say("{} not found.".format(meta_json))
  else:
    emit(meta)

def read_cached(filename):
  meta_json = strip_extension(filename) + ".json"
  if not os.path.exists(meta_json):
    return False

  with open(meta_json, 'r') as f:
    meta = json.load(f)

  return meta

#####
#
def new_metadata(meta_cached):
  new_metadata = dict()
  new_metadata['Exif.Image.DateTime'] = date_taken_from_cached(meta_cached)
  new_metadata['Xmp.dc.title'] = title_from_cached(meta_cached)
  new_metadata['Xmp.dc.subject'] = tags_from_cached(meta_cached)
  new_metadata['Iptc.Application2.Keywords'] = tags_from_cached(meta_cached)
  new_metadata['Exif.Image.ImageID'] = photopage_from_cached(meta_cached)
  new_metadata['Xmp.dc.source'] = photopage_from_cached(meta_cached)
  new_metadata['Exif.Image.Artist'] = owner_from_cached(meta_cached)['realname']
  new_metadata['Xmp.dc.creator'] = [owner_from_cached(meta_cached)['realname']]

  if len(description_from_cached(meta_cached)) > 0:
    new_metadata['Exif.Image.ImageDescription'] = description_from_cached(meta_cached)
    new_metadata['Xmp.dc.description'] = description_from_cached(meta_cached)

  # geo exif
  lat, lng = latlng_from_cached(meta_cached)
  if lat is not None and lng is not None:
    new_metadata['Exif.GPSInfo.GPSLatitude'] = decimal_to_dms_fractions(lat)
    new_metadata['Exif.GPSInfo.GPSLatitudeRef'] = 'N' if lat >= 0 else 'S'
    new_metadata['Exif.GPSInfo.GPSLongitude'] = decimal_to_dms_fractions(lng)
    new_metadata['Exif.GPSInfo.GPSLongitudeRef'] = 'E' if lng >= 0 else 'W'

  return new_metadata

def save_meta(media_path, new_metadata, liverun=False):
  metadata = pyexiv2.ImageMetadata(media_path)
  metadata.read()
  for field in new_metadata:
    metadata[field] = new_metadata[field]

  if not liverun:
    print('would write metadata:')
    print_embedded(metadata)
  else:
    metadata.write()

#####
#

def license_from_cached(meta):
  return LICENSES[int(meta['info']['photo']['license'])]

def date_taken_from_cached(meta):
  return meta['info']['photo']['dates']['taken'].strip()

def title_from_cached(meta):
  return meta['info']['photo']['title']['_content'].strip()

def description_from_cached(meta):
  return meta['info']['photo']['description']['_content'].strip()

def notes_from_cached(meta):
  notes = []
  for note in meta['info']['photo']['notes']['note']:
    notes.append(note)
  return notes

def geo_from_cached(meta):
  return meta['info']['photo'].get('location', dict())
  return location

def woeid_from_cached(meta):
  loc = geo_from_cached(meta)
  return loc.get('woeid', None)

def latlng_from_cached(meta):
  loc = geo_from_cached(meta)
  lat = loc.get('latitude', None)
  lng = loc.get('longitude', None)
  if lat is not None:
    lat = float(lat)
  if lng is not None:
    lng = float(lng)
  return lat, lng

def geo_block_from_cached(meta, key):
  loc = geo_from_cached(meta)
  block = loc.get(key, None)
  if block:
    return block.get('_content', None)

def region_from_cached(meta):
  return geo_block_from_cached(meta, 'region')

def county_from_cached(meta):
  return geo_block_from_cached(meta, 'county')

def country_from_cached(meta):
  return geo_block_from_cached(meta, 'country')

def photopage_from_cached(meta):
  for url in meta['info']['photo']['urls']['url']:
    if url['type'] == 'photopage':
      return url['_content']

def owner_from_cached(meta):
  return meta['info']['photo']['owner']

def tags_from_cached(meta):
  tags = info = exif = people = contexts = []

  # make things a little easier
  info = meta['info']['photo']
  visibility = meta['info']['photo']['visibility']

  if any(meta['exif']):
    exif = meta['exif']['photo']['exif']
  if any(meta['people']):
    people = meta['people']['people']['person']
  if any(meta['contexts']):
    contexts = meta['contexts']

  for tag in info['tags']['tag']:
    tags.append(tag['_content'])

  for person in people:
    tags.append('person:{}'.format(person['realname']))
    tags.append('person_screenname:{}'.format(person['username']))

  for context in contexts:
    for c in contexts[context]:
      if context == 'stat':
        continue
      tags.append("{}:{}".format(context, c['title']))

  if info['isfavorite'] == 1:
    tags.append('flickr_fave')

  # this is fairly verbose given the extraction needed
  tags.append('uploaded:{}'.format(epoch_to_date_str(info['dateuploaded'])))
  tags.append('owner_handle:{}'.format(owner_from_cached(meta)['username']))
  tags.append('owner_nsid:{}'.format(owner_from_cached(meta)['nsid']))
  tags.append('owner:{}'.format(owner_from_cached(meta)['realname']))

  # geo tags
  for geo in [woeid_from_cached, region_from_cached, county_from_cached, country_from_cached]:
    val = geo(meta)
    if val is not None:
      tags.append('{}:{}'.format(geo.__name__.split('_')[0], val))

  # permission tags
  for vis in ['isfriend', 'isfamily', 'ispublic']:
    if visibility[vis] == 1:
      tags.append('visibility:{}'.format(vis[2:]))

  tags.append('license:{}'.format(license_from_cached(meta)))

  return tags