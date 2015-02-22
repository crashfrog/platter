from url_parse import Directory, ReadOnly, perform_query, cvrt
from contextlib import contextmanager
import hashlib
import datetime

term = "[{field}] = '{term}'"
		
class WriteableDirectory(Directory):
	
	def __init__(self, name, context):
		super(WriteableDirectory, self).__init__(name)
		self.writable = True
		result = perform_query("""
SELECT
cntn_pk
FROM platter_view
WHERE
isSpecialAttm IS NULL
AND
""" + "\nAND\n".join([term.format(field=f, term=t) for f, t in context.items()])+';')
		assert(len(result) == 1)
		self.content_key = cvrt(result)
		
# 	def new_file(self, name):
# 		"create a new attachment, attach it by link to content, save and hash the file"
# 		import os
# 		import hashlib
# 		import uuid
# 		#do some stuff
# 		path = ''
# 		#do some stuff
# 		attm_pk = cvrt(perform_query("""
# INSERT INTO
# attachment
# (attm_name,
#  attm_file_filename,		
#  attm_path,
#  attm_checksum
# ) VALUES (
#  '{name}',
#  '{name}',
#  '{path}',
#  '{sum}'
# ) RETURN
# inserted.attm_pk;		
# """))
# 		perform_query("""
# INSERT INTO
# attachmentlink
# (atln_fk_attachment,
#  atln_fk_recordPk,
#  atln_Record
# ) VALUES (
#  {attm_pk},
#  {self.content_key},
#  'Content'
# )
# """)


class Writeable(ReadOnly):
	
	"file-like object that allows for changes."
	
	def __init__(self, name, path, created, modified, size, attachment_pk):
		super(Writeable, self).__init__(name, path, created, modified, size)
		self.pk = attachment_pk
		
	def __getattr__(self, attr):
		'delegate undefined methods to underlying file object, if available'
		getattr(self.file_handle, attr)
	
	@staticmethod
	def from_context(context):
		query = """SELECT Displayname, Path, attm_createdOn, attm_modifiedOn, attm_file_filesize, attm_pk FROM platter_view WHERE isSpecialAttm IS NULL AND\n""" + ("\nAND\n".join([term.format(field=key, term=value) for key, value in context.items()]) or '1=1')+';'
		result = perform_query(query)
		assert(len(result) == 1)
		return Writeable(*result[0])
		
	@contextmanager
	def open(self, path):
		self.hash = hashlib.md5()
		self.file_handle = open(path)
		yield self
		self.close()
		
	def write(self, chars):
		self.hash.update(chars)
		self.file_handle.write(chars)
		
	def close(self):
		sum = self.hash.hexdigest()
		self.file_handle.close()
		query = """UPDATE attachment
SET attm_hash = '{sum}',
    attm_modifiedOn = '{stamp}'
WHERE attm_pk = '{pk}';
""".format(sum=sum, stamp=datetime.datetime.today().isoformat(), pk=self.pk)
		perform_query(query)
		
		
	