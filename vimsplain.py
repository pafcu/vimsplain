# encoding:utf-8
from __future__ import print_function # For python 3 compatibility
import sys
import re
import optparse

CTRL_CHAR = '§'

# TODO: better handling of CTRL, special chars
# Unicode issues with Python 2.x, don't use it!

def fix_help(helpfile):
	"""Fix input vim helpfile"""
	sameas_expr = re.compile(r'same as ([^"][^ ]+|"[^"]+")')

	# Split help by section
	sections = re.split(r'[=]{4,}', helpfile.read())[1:] # First part has no commands
	section_lines = []
	for section in sections:
		section_lines.append([])
		lines = []

		# Join cut lines and removed unused commands
		for i, line in enumerate(section.split('\n')):
			if line == '':
				continue
			if line[0] == '\t' and ('not used' in line or 'reserved' in line):
				continue
			if line[0] == '\t': # Continued line
				lines[-1] = '%s %s'%(lines[-1], line.lstrip())
			elif line[0] == '|': # Normal line
				lines.append(line)

		for line in lines:
			# Clean up messy whitespaces
			line = re.sub(r'[ ]{2,}','\t', line)
			line = re.sub(r'\t{2,}','\t', line)

			parts = line.split('\t')
			if len(parts) < 3:
					print(parts)
					raise Exception

			# Add missing tab between empty note field and explanation
			if not (len(parts[2])>0 and (parts[2][0] == '1' or parts[2][0] == '2')):
				parts[2] = '\t'+parts[2]

			# Skip count commands, handled explicitly
			if parts[1].isdigit() and parts[1] != '0': 
				continue

			# Skip buffer and "start-ex" commands, handled explicitly
			if parts[0] == '|quote|' or parts[0] == '|:|': 
				continue

			if parts[0] == '|@|': # Bug in Vim documentation
				parts[1] = '@{0-9a-zA-Z".=*}'

			line = '\t'.join(parts)
			parts = line.split('\t') # Resplit to get parts separated by inserted tabs
			section_lines[-1].append(parts)
	
	# Fix "same as" by looking for matching commands in the same section
	for section in section_lines:
		for parts in section:
			m = sameas_expr.search(parts[3])
			if m:
				sameas = m.group(1).strip('"') # Sometimes there are quotes around the command
				for parts2 in section:
					if parts2[1] == sameas:
						parts[3] = parts2[3]

	return section_lines

def fix_explanation(m, expl):
	# Replace numeric description in explanation with the value found in the input string
	try:
		if m.group('num') != '': 
			expl = expl.replace('N-1',str(int(m.group(1)) - 1))
			expl = numcom_expr.sub(m.group(1), expl)
		else: # No numberic value in input, use default
			m2 = default_expr.search(expl)
			if m2:
				default = int(m2.group(1))
			else:
				default = 1 # Assume 1 as a default "default"
			expl = expl.replace('N-1', str(default - 1))
			expl = numcom_expr.sub(str(default), expl)
	except IndexError: # Does not have numeric component
		pass

	# Replace buffer description in explanation
	try:
		if m.group('buf') != None:
			expl = re.sub(r'\bx\b',m.group('buf'), expl)
	except IndexError:
		pass

	# Replace {char},{word},... in explanation
	for typ in ['char', 'word', 'count', 'height', 'pattern', 'filter']:
		try:
			expl = re.sub(r'\{%s\}'%typ, m.group(typ), expl)
			expl = re.sub(r'%s'%typ.upper(), m.group(typ), expl)
		except IndexError:
			pass
	return expl

def parse(instr, commands, mode, recording, only_motions=False):
	"""Parse next command in instr"""
	# Remove escapes in normal mode, they do nothing anyway
	while mode == 'normal' and instr.startswith('%s['%CTRL_CHAR):
		instr = instr[2:]

	if instr == '':
		raise ValueError

	# Loop over possible commands
	for (tag, expr, expl, plain, is_motion, expect_motion) in commands[mode]:
		if only_motions and not is_motion: # Sometimes we are only interested in motion commands
			continue

		# Skip command that only applies when recording if not recording
		if recording == False and 'while recording' in expl:
			continue

		m = expr.match(instr) # Check if input matches command
		if m:
			if tag == 'q':
				recording = not recording
			expl = fix_explanation(m,expl)

			newmode = mode
			if tag in mode_mapping:
				if mode != mode_mapping[tag]:
					newmode = mode_mapping[tag]
					#print('(switch to %s mode)'%newmode)

			if expect_motion:
				cmd = instr[0:m.end()]
				motion_match, motion_expl, instr, mode, recording = parse(instr[m.end():],commands,mode, recording, only_motions=True)
				return (cmd+motion_match, expl+' with motion %s'%motion_expl, instr, newmode, recording)
			else:
				try:
					expl += ' from '+m.group('from')
				except (IndexError, TypeError):
					pass
				try:
					expl += ' to '+m.group('to')
				except (IndexError, TypeError):
					pass
				return (instr[0:m.end()], expl, instr[m.end():], newmode, recording)

	raise ValueError

def fix_regexp(regexp):
	"""Fix Vim regex so it can be used in Python's re-module"""
	try:
		regexp = regexp.group(1)
	except AttributeError:
		pass

	m = range_expr.search(regexp)
	if m: # Has invalid range
		end = m.end()
		# Move invalid dash to end of characters
		regexp = regexp[:end]+'-'+regexp[end:]
		regexp = range_expr.sub(r'\1\2', regexp)

	return regexp


# Commands that change mode.
mode_change = {}
mode_change['insert'] = ['a','A','i','I','gI','gi','o','O','c','cc','v_c','v_r','v_s',':startinsert',':append','s']
mode_change['normal'] = ['CTRL-[','i_CTRL-[','i_CTRL-C','i_<Esc>','c_CTRL-\_CTRL-N','c_CTRL-\_GTRL-G','v_CTRL-\_CTRL-N','v_CTRL-\_GTRL-G',':visual',':view']
mode_change['visual'] = ['CTRL_V','V','v','<RightMouse>']
mode_change['ex'] = ['Q']

mode_mapping = dict([(command, mode) for mode in mode_change for command in mode_change[mode]])

special_chars = {'CR':CTRL_CHAR+'M', 'TAB':CTRL_CHAR+'I', 'BS':CTRL_CHAR+'?', 'Esc':CTRL_CHAR+'[', 'NL':CTRL_CHAR+'M', 'Space':' '}

optional_expr = re.compile(r'\\\[(.+?)\\\]') # Needs some extra slashes due to escaping
expr_expr = re.compile(r'{([^m].+?)}') # [^m] needed due to crappy handling of {motion}
expr_pat_expr = re.compile(r'\(\?P\<expr\>\[(.*?)\]\)')
range_expr = re.compile(r'(\W)-(\W)')
numcom_expr = re.compile(r'(?:\bN(th)?\b|\bNmove\b)')
plain_expr = re.compile(r'({.+?}|\[.+?\])')
default_expr = re.compile(r'default (?:is )?(\d+)')

def replace_specials(s):
	s = re.sub('<C-(.)>',lambda m: CTRL_CHAR+m.group(1), s) # Replace some special chars
	s = re.sub('<([A-Za-z]+)>',lambda m: special_chars.get(m.group(1), m.group(0)), s) # Replace some special chars
	return s

def parse_commands(fixed_lines):
	commands = {}
	for key in mode_change:
		commands[key] = []

	motions = set([])
	for nsection, lines in enumerate(fixed_lines):
		for i, parts in enumerate(lines):
			tag = parts[0][1:-1] # Remove | around tag
			command = parts[1]
			note = parts[2]

			plain_command = plain_expr.sub('',command) # Remove optional parts and parameters to get "plain" command

			command = command.replace('CTRL-',CTRL_CHAR) # Replace control characters
			command = command.replace(' ','') # Remove whitespace in commands
			command = replace_specials(command)

			# Escape all text except inside {}
			regexp_texts = re.findall(r'\{.*?\}', command)
			for j, regexp in enumerate(regexp_texts): # Fix python <-> vim compatibility issues
				regexp_texts[j] = fix_regexp(regexp)
			command = re.escape(command)
			command = re.sub(r'\\{.*?\\}',lambda x: regexp_texts.pop(), command) # Reinsert the regexes

			command = command.replace(r'\[\"x\]',r'(\"(?P<buf>.))?') # Replace buffer commands. BUG: Don't use ., check valid registers

			command = optional_expr.sub(r'(?:\1)?',command) # Convert optional part into regex

			# Check if command is an ex command
			if plain_command[0] == ':':
				# Insert possible range after initial ':'
				# Some ex commands don't allow ranges, but add it anyway since index doesn't specify which do
				line_marker = r"\d+|[.$%]|['].|[/].*?([/])?|[?].*?([?])?|[\][/]|[\][?]|[\][&]"
				range_expr = r'(?P<from>%s)?([,;](?P<to>%s))?'%(line_marker,line_marker)
				idx = command.index(':')
				command = command[:idx+1]+range_expr+command[idx+1:]

				command += r'(?P<args>[^A-Za-z].*?)?' # Some commands take arguments. Again, impossible to say which
				command += r'\%sM'%CTRL_CHAR # Ex commands expect a newline at the end

			# Check if command takes numeric argument
			if numcom_expr.search(parts[3]) and not r'\{count\}' in command:
				command = '(?P<num>\d*)'+command

			# Convert some placeholders into appropriate regexes
			command = command.replace(r'{char}','(?P<char>[^ ])')
			command = command.replace(r'{word}','(?P<word>[^ ]+)')
			command = command.replace(r'{count}','(?P<count>\d+)')
			command = command.replace(r'{height}','(?P<height>\d+)')
			command = command.replace(r'{pattern}','(?P<pattern>.*?)')
			command = command.replace(r'{filter}','(?P<filter>.*?)'+special_chars['CR'])

			#command = expr_expr.sub(lambda x: '(?P<expr>['+fix_regexp(x)+'])', command) # Handle remaining {} as regexps
			command = expr_expr.sub(lambda x: '['+fix_regexp(x)+']', command) # Handle remaining {} as regexps

			if note == '1' or nsection == 2 or tag in motions:
				is_motion = True
				motions.add(tag)
			else:
				is_motion = False

			expect_motion = command.endswith('{motion}')

			tup = [tag, re.compile(command.replace('{motion}','')), parts[3], plain_command, is_motion, expect_motion]
			# Check which modes commands belong to
			if nsection > 0 and nsection != 7 and nsection != 8:
				commands['normal'].insert(0,tup)
				commands['visual'].insert(0,tup)
				if nsection == 9: # Ex mode commands
					tup2 = (tup[0], re.compile(tup[1].pattern[2:]), tup[2], tup[3], tup[4], tup[5]) # Recompile expresison but with leading '\:' removed
					commands['ex'].insert(0,tup2)
			elif nsection == 7: # Visual mode command
				# This will add some duplicate commands since some are given as normal mode commands as well
				# Insert at beginning to make sure these are found first
				commands['visual'].insert(0,tup)
			elif nsection == 0: # Insert mode command
				commands['insert'].insert(0,tup)

	return commands

commands = parse_commands(fix_help(open('index.txt')))

parser = optparse.OptionParser(description='Explain a sequence of Vim commands.')
parser.add_option('--convert_special', dest='convert', action='store_true', help='Interpret sequences in angle brackets as special characters (e.g. <CR>).')
options, args = parser.parse_args()
instr = args[0]
if options.convert:
	instr = replace_specials(instr)

mode = 'normal'
recording = False

while instr != '':
	if mode == 'insert':
		inserted = ''
		j = 0
		# Copy inserted text
		while j < len(instr) and instr[j] != CTRL_CHAR: # BUG: Only handles CTRL-commands
			inserted += instr[j]
			j += 1
		if inserted != '':
			print('\t\tText: %s'%inserted)
		instr = instr[j:]

		# Check for commands
		matched = None
		if instr[j:] != '':
			matched, explanation, instr, mode, recording = parse(instr, commands, mode, recording)
		if matched:
			print('\t\tCommand: %s\t%s'%(matched, explanation))
	else:
		matched, explanation, instr, mode, recording = parse(instr, commands, mode, recording)
		print('%s\t%s'%(matched, explanation))
