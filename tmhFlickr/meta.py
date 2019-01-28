import json
import os
import pyexiv2
from .utils import say, strip_extension, emit, epoch_to_date_str

def inspect_embedded(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
  print_embedded(metadata)

def print_embedded(metadata):
  keys = metadata.xmp_keys + metadata.exif_keys + metadata.iptc_keys
  for key in keys:
    say('{}: {}'.format(key, metadata[key].raw_value))

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
  if len(description_from_cached(meta_cached)) > 0:
    new_metadata['Exif.Image.ImageDescription'] = description_from_cached(meta_cached)
    new_metadata['Xmp.dc.description'] = description_from_cached(meta_cached)
  new_metadata['Exif.Image.ImageID'] = photopage_from_cached(meta_cached)
  new_metadata['Xmp.dc.source'] = photopage_from_cached(meta_cached)
  new_metadata['Exif.Image.Artist'] = owner_from_cached(meta_cached)['realname']
  new_metadata['Xmp.dc.creator'] = [owner_from_cached(meta_cached)['realname']]

  # TODO
  # add geo if we have it
  # add flickr perm
  # add license
  return new_metadata

def save_meta(media_path, new_metadata):
  metadata = pyexiv2.ImageMetadata(media_path)
  metadata.read()
  # print_embedded(metadata)
  # print('------------------------')
  for field in new_metadata:
    metadata[field] = new_metadata[field]
  # print_embedded(metadata)
  metadata.write()

#####
#

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
  return loc.get('latitude', None), loc.get('longitude', None)

def photopage_from_cached(meta):
  for url in meta['info']['photo']['urls']['url']:
    if url['type'] == 'photopage':
      return url['_content']

def owner_from_cached(meta):
  return meta['info']['photo']['owner']

def flickr_perms_from_cached(meta):
  key = meta['info']['photo']['visibility']
  perms = []
  if key['isfriend'] == 1:
    perms.append('friends')
  if key['isfamily'] == 1:
    perms.append('family')
  if key['ispublic'] == 1:
    perms.append('public')

  return '& '.join(perms)

def tags_from_cached(meta):
  tags = info = exif = people = []

  # make things a little easier
  info = meta['info']['photo']
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

  woeid = woeid_from_cached(meta)
  if woeid is not None:
    tags.append('woeid:{}'.format(woeid))

  return tags