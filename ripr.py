# https://python3-exiv2.readthedocs.io/en/latest/tutorial.html#reading-and-writing-xmp-tags

# TODO
# add checks for errors- try catch
# add data taken check - some of these are missing them
# move title into description as well
# add in a text search when getting photosOf (not just PhotosOf and tags)
# fix serialization bug. F object doesn't pickle properly
# add "auth" flow helper


import flickr_api as f
import os
import pickle
import pyexiv2
import sys
import threading
from pprint import pprint as pp
from math import ceil

f.set_auth_handler("mharris_auth.txt")

PER_PAGE=400
EXTRAS=['description, license, date_upload, date_taken, owner_name, icon_server, original_format, '
		'last_update, geo, tags, machine_tags, o_dims, media, path_alias, url_t, url_l, url_o']
THREADS=8

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
	user = f.test.login()
	return user

def get_user(username):
	user = f.Person.findByUserName(username)
	return user

def get_photo_by_id(id):
	p = f.Photo(id)
	return p.getInfo()

# Returns a list of groups to which you can add photos.
def get_groups():
	return get_with_pagination(f.Group.getGroups)

# Return photos from the given user's photostream. Only photos visible to the calling user will be returned. This method must be authenticated;
def get_user_photos(user, limit=5):
	return get_with_pagination(user.getPhotos, extras=EXTRAS)

def get_photo_meta(photo):
	exif = []
	try:
		exif = photo.getExif()
	except f.flickrerrors.FlickrAPIError as e:
		if e.code == 2: # permission denied
			pass
		else:
			raise e

	data = {
		'info': photo.getInfo(),
		'exif': exif,
		'comments': photo.getComments(),
		'contexts': photo.getAllContexts(),
		'people': photo.getPeople()
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
		full_path = os.path.join(save_path, "{}.bin".format(filename))
		if os.path.isfile(full_path):
			print("{} already retrieved. skipping.".format(full_path))
			continue
		
		# if no size_label is specified the largest available is retrieved
		photo.save(os.path.join(save_path, filename))

		# save the meta to binary (just in case)
		serialize_to_file(meta, save_path, filename)
		update_photometa(meta, save_path, filename)

def serialize_to_file(obj, save_path, filename):
	print('saving meta to {}'.format(os.path.join(save_path, filename)))

	# objects are a mess so dump to json
	


	pickle.dump(obj, open('{}.bin'.format(os.path.join(save_path, filename)), "wb" ))


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
	
	metadata['Exif.Image.ImageDescription'] = meta['info']['description']
	metadata['Xmp.dc.description'] = meta['info']['description']
	
	metadata['Exif.Image.ImageID'] = meta['info']['urls']['url'][0]['text']
	metadata['Xmp.dc.source'] = meta['info']['urls']['url'][0]['text']
	
	metadata['Exif.Image.Artist'] = meta['info']['owner'].username
	metadata['Xmp.dc.creator'] = [meta['info']['owner'].username]

	subjects = []

	# if 'Iptc.Application2.Keywords' in metadata.iptc_keys:
	# 	subjects = metadata['Iptc.Application2.Keywords'].value

	# tags
	for tag in meta['info']['tags']:
		subjects.append(tag.text)

	for person in meta['people']:
		subjects.append("person:{}".format(person.username))

	for contexts in meta['contexts']:
		for context_subtype in contexts:
			subjects.append("context:{}".format(context_subtype.title))

	subjects.append("owner:{}".format(meta['info']['owner'].username))

	metadata['Xmp.dc.subject'] = subjects
	metadata['Iptc.Application2.Keywords'] = subjects
	metadata.write()

def inspect_meta(filename):
	metadata = pyexiv2.ImageMetadata(filename)
	metadata.read()
	keys = metadata.xmp_keys + metadata.exif_keys +	metadata.iptc_keys
	for key in keys:
		print('{}: {}'.format(key, metadata[key].raw_value))

if len(sys.argv) == 2 and sys.argv[1] == 'go':
	cindy = get_user('cindyli')
	photo_list = get_photosof(cindy, 'cindyli,"cindy li",cindylidesign', ['cindy li', 'cindyli'])
	print('Got {} Photos'.format(len(photo_list)))
	process_photolist(photo_list)

# pp(get_user_photos(cindy))
# pp(get_groups())

# in python3 to use this file do
# exec(open("ripr.py").read())