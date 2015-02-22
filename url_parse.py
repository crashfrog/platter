import sys
import collections
from functools import partial
import pymssql

#url = sys.argv[1].split('/')

select = """SELECT
DISTINCT
[{level}]
FROM platter_view
WHERE
[{level}] IS NOT NULL
AND
"""

term = "[{field}] = '{term}'"

platform_aliases = {'miseq':'Illumina MiSeq sequence',
					'hiseq':'Illumina HiSeq sequence',
					'nextseq':'Illumina NextSeq sequence',
					'pacbio':'PacBio RS sequence',
					'454':'Roche 454 sequence',
					'nanopore':'Oxford Nanopore sequence',
					'misc':'Unknown sequence',
					}
					
simple_query_cache = dict() #this cache is probably not doing anything
					
def parse(url, *args, **kwargs):
	if '.DS_Store' in url:
		return
	if '._' in url:
		return
	tokens = filter(lambda t: t, url.split(';')[0].split('/'))
	#print tokens
	return root(tokens, collections.OrderedDict(), *args, **kwargs)

def query(level, nulls=(), nonnulls=(), **kwargs):
	qy = select.format(level=level)
	qy += ''.join(['[{}] IS NULL AND\n'.format(fld) for fld in nulls])
	qy += ''.join(['[{}] IS NOT NULL AND\n'.format(fld) for fld in nonnulls])
	return qy + ("\nAND\n".join([term.format(field=key, term=value) for key, value in kwargs.items()]) or '1=1')+';'

def perform_query(query="SELECT * FROM platter_view WHERE 1=0;"):
	print query
	def put_in_cache(results):
		simple_query_cache[query] = results
		return results
	def connect_and_query(query):
		conn = pymssql.connect('cfvcesqlprep.fda.gov', 'slims', 'slims', 'GIMSPrepDB')
		cursor = conn.cursor()
		cursor.execute(query)
		return cursor.fetchall()
	return simple_query_cache.get(query, put_in_cache(connect_and_query(query)))

# Root = collections.namedtuple('Root', ('name', 'modules'))
# 
# roots = (Root('strains', (taxonomy, base)),
# 		 Root('cfsans', (accessions, base)),
# 		 Root('platforms', (sequences)),
# 		 Root('assemblies', (assemblies)),
# 		 Root('annotations', (annotations)),

def cvrt(tuple_or_string):
	if type(tuple_or_string) == tuple:
		return cvrt(tuple_or_string[0])
	return str(tuple_or_string)
		 
class Element(object):

	def __init__(self, name):
		self.name = name
		
	def __repr__(self):
		return self.name
		
	def __iter__(self):
		return iter([self])
		
		 
class Directory(Element):
	
	def containing(self, *items):
		#return [Directory(cvrt(q)) for q in items]
		self.contents += [cvrt(q) for q in items]
		return self
		
	def __init__(self, name):
		self.name = name
		self.contents = list()
		self.writable = False
		
	def __iter__(self):
		return iter(self.contents)
		
	def __repr__(self):
		return self.name + '/'
		
	
class ReadOnly(Element):

	def __init__(self, name, path, created, modified, size):
		self.name = name
		self.path = path
		self.creation_date = created
		self.modify_date = modified
		self.size = size
		
	def __repr__(self):
		return "File: {} ({})".format(self.name, self.path)
	
	@staticmethod
	def from_context(context, *args, **kwargs):
		query = """SELECT Displayname, Path, attm_createdOn, attm_modifiedOn, attm_file_filesize FROM platter_view WHERE isSpecialAttm IS NOT NULL AND\n""" + ("\nAND\n".join([term.format(field=key, term=value) for key, value in context.items()]) or '1=1')+';'
		result = perform_query(query)
		if not result:
			return
		assert(len(result) == 1)
		return ReadOnly(*result[0])
	

	
class NotFoundException(Exception):
	pass

"""strains/Salmonella/enterica/enterica/Heidelberg/CFSAN001992/asm
															  /seq
															  /ann
															  /atc
   cfsans/CFSAN001992/asm
					 /seq
					 /ann
					 /atc
					 
   platforms/miseq/
   
   assemblies/CFSAN001992/SPAdes/3.0/CFSAN001992.fasta
   
   annotations/CFSAN001992/PGAP/
   
   barcodes/ASM
		   /SEQ
		   /ANN
		   /EXT
		   /ISO
		   /SMP
		   /ORG
					 
"""

def notFound(tokens, context, *args, **kwargs):
	print tokens, context
	raise NotFoundException()


def root(tokens, context, *args, **kwargs):
	if not tokens:
		return Directory('').containing(*paths.keys())
	rt = tokens.pop(0)
	return paths.get(rt, notFound)(tokens, context, name=rt, *args, **kwargs)

def base(tokens, context, next_func, *args, **kwargs):
	if not tokens:
		return Directory(context.values()[-1]).containing('asm', 'seq', 'ann', 'atc')
	token = tokens.pop(0)
	if 'asm' in token:
		return assemblies(tokens, context, name='asm', *args, **kwargs)
	if 'seq' in token:
		return sequences(tokens, context, name='seq', *args, **kwargs)
	if 'ann' in token:
		return annotations(tokens, context, name='ann', *args, **kwargs)
	if 'atc' in token:
		context['Type'] = 'Isolate'
		return writeable_endpoint(tokens, context, name='atc', *args, **kwargs)
	return next_func(tokens, context, *args, **kwargs)
	
	
# def cfsans(next_func, tokens, context, *args, **kwargs):
# 	if not tokens:
# 		return Directory.containing(*perform_query(query('CfsanAccession')))
# 	context['CfsanAccession'] = tokens.pop(0)
# 	return next_func(tokens, context, *args, **kwargs)
# 	
# def barcodes(next_func, tokens, context, *args, **kwargs):
# 	if not tokens:
# 		return Directory.containing(*perform_query(query('BarcodePrefix', **context)))
# 	context['Barcode'] = tokens.pop(0)
# 	return next_func(tokens, context, *args, **kwargs)
	
def abstract_endpoint(tokens, context, next_func, fields=('Filename',), name=None, *args, **kwargs):
	if not name:
		name = context.values()[-1]
	for field in fields:
		if not tokens:
			return Directory(name).containing(*perform_query(query(field, **context)))
		context[field] = tokens.pop(0)
		name = context.values()[-1]
	return next_func(tokens=tokens, context=context, name=name, *args, **kwargs)
	
cfsans = partial(abstract_endpoint, fields=('CfsanAccession', ))
barcodes = partial(abstract_endpoint, fields=('BarcodePrefix', 'Barcode'))


def taxonomy(tokens, context, next_func, name='strains', *args, **kwargs):
	
	if not tokens:
		return Directory(name).containing(*(perform_query(query('Genus', **context))))
	context['Genus']= genus = tokens.pop(0)
	if not tokens:
		return Directory(genus).containing(*(perform_query(query('Species', **context))))
	context['Species'] = species = tokens.pop(0)
	
	if not tokens:
		return Directory(species).containing(*(perform_query(query('Subspecies', **context)) + 
															perform_query(query('Strain', nulls=('Subspecies', 'Serovar'), **context))))
	
	context['Subspecies'] = subspecies = tokens.pop(0)
	if not tokens:
		return Directory(subspecies).containing(*(perform_query(query('Serovar', **context)) +
												  perform_query(query('Strain', nulls=('Serovar',), **context))))
	context['Serovar'] = serovar = tokens.pop(0)
	if not tokens:
		return Directory(serovar).containing(*(perform_query(query('Strain', **context))))
	context['Strain'] = tokens.pop(0)
	return next_func(tokens, context, *args, **kwargs)
		
	


		
# def assemblies(tokens, context, *args, **kwargs):
# 	if not tokens:
# 		return Directory.containing(perform_query(query('Assembler', **context)))
# 	context['Assembler'] = tokens.pop(0)
# 	if not tokens:
# 		return Directory.containing(perform_query(query('Version', **context)))
# 	context['Version'] = tokens.pop(0)
# 	if not tokens:
# 		return Directory.containing(perform_query(query('Filename', **context)))
# 	context['Filename'] = tokens.pop(0)
# 	return Read-Only.from_context(context, *args, **kwargs)
# 		
def sequences(tokens, context, next_func, name=None, *args, **kwargs):
	if not name:
		name = context.values()[-1]
	if not tokens:
		return Directory(name).containing(*platform_aliases.keys())
	name = tokens.pop(0)
	context['Type'] = platform_aliases[name]
	if not tokens:
		return Directory(name).containing(*perform_query(query('Barcode', **context)))
	context['Barcode'] = tokens.pop(0)
	return next_func(tokens, context, *args, **kwargs)

def read_only_endpoint(tokens, context, *args, **kwargs):
	if not tokens:
		#return Directory.containing('atm') + Directory.containing(*perform_query("""SELECT Filename FROM platter_view WHERE isSpecialAttm IS NOT NULL AND\n""" + ("\nAND\n".join([term.format(field=key, term=value) for key, value in context.items()]) or '1=1')+';'))
		return Directory(context.values()[-1]).containing('atc', *perform_query(query('Filename', nonnulls=('isSpecialAttm',), **context)))
	token = tokens.pop(0)
	if 'atc' in token:
		return writeable_endpoint(tokens, context, *args, **kwargs)
	return ReadOnly.from_context(context, *args, **kwargs)
	

	
def writeable_endpoint(tokens, context, name='atc', *args, **kwargs):
	from writable import WriteableDirectory, Writeable
	if not tokens:
		return WriteableDirectory(name, context).containing(*perform_query(query('Filename', nulls=('isSpecialAttm',), **context)))
	context['Filename'] = tokens.pop(0)
	return Writeable.from_context(context, *args, **kwargs)
	
assemblies = partial(abstract_endpoint, next_func=read_only_endpoint, fields=('AssemblyVersion', 'Barcode'))
annotations = partial(abstract_endpoint, next_func=read_only_endpoint, fields=('AnnotationPipeline', 'Barcode'))
#attachments = partial(abstract_endpoint, next_func=writeable_endpoint, fields=('Filename',))
sequences = partial(sequences, next_func=read_only_endpoint)
	
base_endpoint = partial(base, next_func=notFound)

paths = {
	'strains':partial(taxonomy, next_func=base_endpoint),
	'cfsans':partial(cfsans, next_func=base_endpoint),
	'platforms':sequences,
	'assemblies':assemblies,
	'annotations':annotations,
	'barcodes':partial(barcodes, next_func=read_only_endpoint),
}
	
if __name__ == '__main__':
	try:
		response = parse(sys.argv[1])
	except IndexError:
		response = parse('')
	print "\n".join([str(r) for r in response]) or response
	
	