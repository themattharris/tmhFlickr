from pprint import pprint as pp
from fractions import Fraction
import datetime
import json
import math
import os

def emit(obj):
  pp(obj)

def emit_dict(obj):
  pp(obj.__dict__)

def say(message):
  print(message)

def say_with_photo(photo, message):
  say('{}: {}'.format(extract_filename(photo.getPhotoFile()), message))

def extract_filename(url):
  return remove_zzs(os.path.basename(url))

def remove_zzs(str):
  suffix = '?zz=1'
  # this suffix gets put into the filename so remove it
  if str.endswith(suffix):
    str = str[:-(len(suffix))]
  return str

def epoch_to_date_str(timestamp):
  return str(datetime.datetime.fromtimestamp(int(timestamp)))

def strip_extension(filename):
  return os.path.splitext(filename)[0]

def uniq_by_id(photo_list):
  seen = set()
  uniq = []
  for p in photo_list:
    if p.id not in seen:
      uniq.append(p)
      seen.add(p.id)
  return uniq

def write_to_file(content, save_path):
  with open(save_path, 'w') as outfile:
    json.dump(content, outfile)

def decimal_to_fraction(decimal):
  remainder, degrees = math.modf(abs(decimal))
  remainder, minutes = math.modf(remainder * 60)
  remainder, seconds = math.modf(remainder * 60)
  return [Fraction(n) for n in (degrees, minutes, seconds)]