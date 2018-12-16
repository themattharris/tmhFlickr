# https://python3-exiv2.readthedocs.io/en/latest/tutorial.html#reading-and-writing-xmp-tags

# TODO
# add checks for errors- try catch
# add data taken check - some of these are missing them
# (done) move title into description as well
# (done) add in a txt search when getting photosOf (not just PhotosOf and tags)
# (done) fix serialization bug. F object doesn't pickle properly
# (done) save meta to disc
# (done) add "auth" flow helper

import flickr_keys
import json
import flickr_api as f
import os
import pyexiv2
import sys
import threading
from flickr_api.api import flickr
from pprint import pprint as pp
from math import ceil

PER_PAGE=400
EXTRAS=['description, license, date_upload, date_taken, owner_name, icon_server, original_format, '
        'last_update, geo, tags, machine_tags, o_dims, media, path_alias, url_t, url_l, url_o']
THREADS=8

f.set_keys(api_key = flickr_keys.API_KEY, api_secret = flickr_keys.API_SECRET)

def authorize():
  a = f.auth.AuthHandler()
  perms = "read"
  url = a.get_authorization_url(perms)
  print("Go here and then come back: {}".format(url))
  verifier = input('Enter the oauth_verifier value from the webpage shown after you authorized access: ')
  a.set_verifier(verifier)
  f.set_auth_handler(a)
  user = whoami()

  creds_file = "{}_auth.txt".format(user.username)
  a.save(creds_file)
  print("Saved as {}".format(creds_file))

def emit(obj):
  pp(obj)

def emit_dict(obj):
  pp(obj.__dict__)

def uniq_photolist(photo_list):
  seen = set()
  uniq = []
  for p in photo_list:
    if p.id not in seen:
      uniq.append(p)
      seen.add(p.id)
  return uniq

def extract_filename(url):
  return os.path.splitext(os.path.basename(url))[0]

def enable_cache(enable):
  if enable:
    f.enable_cache()
  else:
    f.disable_cache()

def get_with_pagination(func, limit=None, **kwargs):
  data = []
  current_page = 1
  total_pages = 2

  while current_page <= total_pages:
    if current_page > 1:
      print('Requesting page {} of {}'.format(current_page, total_pages))

    res = func(
      **kwargs,
      per_page = PER_PAGE,
      page = current_page
    )
    current_page += 1
    total_pages = res.info.pages
    data = data + res.data      

    if limit is not None and current_page >= limit:
      break
  return data 

def whoami():
  return f.test.login()

def get_user(username):
  return f.Person.findByUserName(username)

def get_photo_by_id(id):
  p = f.Photo(id=id)
  p.getInfo()
  return p

# Returns a list of groups to which you can add photos.
def get_groups():
  return get_with_pagination(f.Group.getGroups)

# Return photos from the given user's photostream. Only photos visible to the calling user will be returned. This method must be authenticated;
def get_user_photos(user, limit=5):
  return get_with_pagination(user.getPhotos, extras=EXTRAS)

def get_photo_meta(photo):
  exif = []
  try:
    exif = json.loads(flickr.photos.getExif(photo_id=photo.id, format="json", nojsoncallback=1))
  except f.flickrerrors.FlickrAPIError as e:
    if e.code == 2: # permission denied
      pass
    else:
      raise e

  data = {
    'info': json.loads(flickr.photos.getInfo(photo_id=photo.id, format="json", nojsoncallback=1)),
    'exif': exif,
    'comments': json.loads(flickr.photos.comments.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
    'contexts': json.loads(flickr.photos.getAllContexts(photo_id=photo.id, format="json", nojsoncallback=1)),
    'people': json.loads(flickr.photos.people.getList(photo_id=photo.id, format="json", nojsoncallback=1)),
  }
  return data

# Returns a list of pool photos for a given group, based on the permissions of the group and the user logged in (if any).
def get_group_photos(group):
  return get_with_pagination(group.getPhotos, extras=EXTRAS)

# matt nsid: 20071329@N00
# cindy nsid: 43082001@N00
def get_photosof(user, tags=None, text=None):
  print('Requesting photosOf {}'.format(user.username))
  data = get_with_pagination(user.getPhotosOf, extras=EXTRAS)
  if tags is not None:
    print('Requesting photos with tags: {}'.format(tags))
    data = data + get_with_pagination(f.Photo.search, extras=EXTRAS, tags=tags)

  if text is not None:
    if not isinstance(text, list):
      text = [text]
    for t in text:
      print('Requesting photos using text search of: {}'.format(t))
      data = data + get_with_pagination(f.Photo.search, extras=EXTRAS, text=t)

  return uniq_photolist(data)

# iterate over the photos
# download them, 
# store them in an output directory under the yyyy-mm-dd they were taken
# set the meta from the meta
# store the meta in a json blob with the same name
def process_photolist(photo_list):
  from threading import Thread
  from itertools import zip_longest

  size = ceil(len(photo_list) / THREADS)
  bags = zip(*(iter(photo_list),) * size)
  print("Processing across {} threads with bag size {}".format(THREADS, size))
  for bag in bags:
    t = Thread(target=process_photolist_for_real, args=(bag,))
    t.start()

def process_photolist_for_real(photo_list, limit=None):
  processed = 0
  for photo in photo_list:
    if processed == limit:
      break
    processed += 1

    filename = extract_filename(photo.getPhotoFile())
    print('(T{}): Processing {} ({}/{})'.format(threading.get_ident(), filename, processed, len(photo_list)))
    meta = get_photo_meta(photo)

    save_path = os.path.join('/Users', 'themattharris', 'Downloads', 'flickr', photo.taken.split()[0])

    if not os.path.exists(save_path):
      os.makedirs(save_path)

    # don't do anything if the file already exists
    full_path = os.path.join(save_path, "{}.jpg".format(filename))
    if os.path.isfile(full_path):
      print("{} already retrieved. skipping.".format(full_path))
      continue
    
    # if no size_label is specified the largest available is retrieved
    photo.save(os.path.join(save_path, filename))
    # save the meta to json for future use
    serialize_to_file(meta, save_path, filename)
    # update the image meta
    update_photometa(meta, save_path, filename)

def serialize_to_file(meta, save_path, filename):
  save_path = os.path.join(save_path, "{}.json".format(filename))
  print('saving meta to {}'.format(save_path))
  with open(save_path, 'w') as outfile:
    json.dump(meta, outfile)

def update_photometa(meta, save_path, filename):
  print('Updating meta of {}'.format(os.path.join(save_path, filename)))
  jpgfilename = '{}.jpg'.format(os.path.join(save_path, filename))
  # from inspection - looks like tags are already in there, as is geo
  # need to set description and title though
  metadata = pyexiv2.ImageMetadata(jpgfilename)
  metadata.read()

  if not 'DateCreated' in metadata.exif_keys:
    # if we're here it likely means we didn't get the "original" 
    # image so we need to copy some fields
    metadata['Exif.Image.DateTime'] = meta['exif']
    for exif in meta['exif']:
      metadata['Exif.Image.{}'.format(exif.tag)] = exif.raw
            
  metadata['Xmp.dc.title'] = meta['info']['title']
    
  description = "{}\n{}".format(meta['info']['title'], meta['info']['description'])
  metadata['Exif.Image.ImageDescription'] = description
  metadata['Xmp.dc.description'] = description
  
  metadata['Exif.Image.ImageID'] = meta['info']['urls']['url'][0]['text']
  metadata['Xmp.dc.source'] = meta['info']['urls']['url'][0]['text']
  
  metadata['Exif.Image.Artist'] = meta['info']['owner'].username
  metadata['Xmp.dc.creator'] = [meta['info']['owner'].username]

  subjects = []
  subjects.append("owner:{}".format(meta['info']['owner'].username))
  
  # if 'Iptc.Application2.Keywords' in metadata.iptc_keys:
  #   subjects = metadata['Iptc.Application2.Keywords'].value

  for tag in meta['info']['tags']:
    subjects.append(tag.text)

  for person in meta['people']:
    subjects.append("person:{}".format(person.username))

  for contexts in meta['contexts']:
    for context_subtype in contexts:
      subjects.append("context:{}".format(context_subtype.title))

  metadata['Xmp.dc.subject'] = subjects
  metadata['Iptc.Application2.Keywords'] = subjects
  metadata.write()

def inspect_meta(filename):
  metadata = pyexiv2.ImageMetadata(filename)
  metadata.read()
  keys = metadata.xmp_keys + metadata.exif_keys + metadata.iptc_keys
  for key in keys:
    print('{}: {}'.format(key, metadata[key].raw_value))

if len(sys.argv) > 1 and sys.argv[1] == 'fetch':
  f.set_auth_handler("cindyli_auth.txt")
  cindy = get_user('cindyli')
  photo_list = get_photosof(cindy, 'cindyli,"cindy li",cindylidesign', ['cindy li', 'cindyli'])
  print('Got {} Photos'.format(len(photo_list)))
  process_photolist(photo_list)
elif len(sys.argv) > 1 and sys.argv[1] == 'auth':
  authorize()
elif len(sys.argv) > 1 and sys.argv[1] == 'inspect':
  inspect_meta(sys.argv[2])

# photo = get_photo_by_id(31937834368)

# in python3 to use this file do
# exec(open("ripr.py").read())

# example use
# python3 ripr.py inspect /Users/themattharris/Downloads/flickr/2017-02-25/31937834368_83d168a05c_o.jpg
# python3 ripr.py auth
# python3 ripr.py fetch