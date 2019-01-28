import json
import os
import pyexiv2
from .utils import say, strip_extension, emit, epoch_to_date_str

def inspect_embedded(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
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
  if not os.path.exists(filename):
    return False

  with open(filename, 'r') as f:
    meta = json.load(f)

  return meta

def process_cached(meta):
  say('processing meta')

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
  tags = []

  # make things a little easier
  info = meta['info']['photo']
  exif = meta['exif']['photo']['exif']
  people = meta['people']['people']['person']
  contexts = meta['contexts']

  for tag in info['tags']['tag']:
    tags.append(tag['_content'])

  for person in people:
    tags.append('person:{}'.format(person['realname']))
    tags.append('person_screenname:{}'.format(person['username']))

  # this is fairly verbose given the extraction needed
  tags.append('uploaded:{}'.format(epoch_to_date_str(info['dateuploaded'])))
  tags.append('owner_handle:{}'.format(info['owner']['username']))
  tags.append('owner_nsid:{}'.format(info['owner']['nsid']))
  tags.append('owner:{}'.format(info['owner']['realname']))

  woeid = woeid_from_cached(meta)
  if woeid is not None:
    tags.append('woeid:{}'.format(woeid))

  return tags