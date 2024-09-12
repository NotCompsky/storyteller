#!/usr/bin/env python3


import select
import sys
import termios
import os
import subprocess
import json
import random
import zlib
from datetime import datetime as dt
from hash_utils import gethashoftext
import ctypes # NOTE: Must precede `import resource` to avoid weird error
clib = None



models:dict = {}

volume:float = 1.0

delay_between_sentences:str = "0.2"
delay_between_lines:str = "0.5"
delay_from_dotdotdot:str = "0.5"
delay_from_comma:str = "0.2"
delay_from_dash:str = "0.2"
delay_from_colon:str = "0.2"
delay_from_semicolon:str = "0.2"

ENUM_SLEEP:int = 0
ENUM_VOICE:int = 1
ENUM_BGAUDIO:int = 2 # TODO
ENUM_FGAUDIO:int = 3
ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES:int = 4
ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES:int = 5
ENUM_START_OF_FILE:int = 6
ENUM_END_OF_FILE:int = 7
ENUM_REPEAT_UNTIL_ZERO:int = 8
ENUM_IFCLOCKTIMEGT:int = 9
ENUM_IFCLOCKTIMEGT_END:int = 10
ENUM_IFBOOL:int = 11
ENUM_IFBOOL_END:int = 12
ENUM_torepeatifenterpressed:int = 13

def set_bg_audio(fp:str, volumemult:float):
	return subprocess.Popen(["cvlc","--gain",str(volume*volumemult),"--volume-step","100","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart",fp])

def was_key_pressed_since_last_check():
	b:bool = (len(select.select([sys.stdin], [], [], 0.0)[0]) != 0)
	if b:
		# True - so clear it
		os.read(sys.stdin.fileno(), 1024*1024)
	return b

def getpromptval(promptstr:str, suppress_prompt:bool):
	if suppress_prompt:
		return True
	b:bool = False
	while True:
		s:str = input("[y/n]: "+promptstr)
		if s == "y":
			b = True
			break
		if s == "n":
			break
	return b

def sleep_with_slight_audio(t:float):
	print("SLEEPING",t)
	while t > 0.0:
		clib.playAudio(b"/media/vangelic/DATA/tmp/tts/libritts719_b9143b3a92f062c7ac7b0691affb8fa840411724", 0.0, 0.0, 0.001)
		t -= 0.59

def check_headphones_connected():
	try:
		result = subprocess.run(['amixer', 'sget', 'Headphone'], capture_output=True, text=True, check=True)
		output_lines = result.stdout
		return " [on]\n" in output_lines
	except subprocess.CalledProcessError:
		return False

def t2human(x:float):
	if x < 600.0:
		return str(x)+"s"
	if x < 7200.0:
		return str(x/60)+"min"
	return str(x/3600)+"hr"

def gzip_compress(contents:bytes):
	CO = zlib.compressobj(level=9, wbits=31)
	return CO.compress(contents)+CO.flush()

def gzip_decompress(contents:bytes):
	return zlib.decompress(contents, wbits=31)

def strip_trailing_comment(s:str):
	return re.sub(" *#.*$", "", s)

def pre_process_line(line:str):
	line = re.sub("\\bn[*][*][*][*]r(s|)\\b", "nigger\\1", line)
	line = re.sub("\\bGreg\\b", "Adam", line)
	line = re.sub("\\b[Ww]hite girlfriend(s|)\\b","white daughter\\1", line)
	line = re.sub("\\bAryan girlfriend(s|)\\b","Aryan daughter\\1", line)
	line = re.sub("\\bBBC\\b", "bee bee sea", line)
	line = re.sub("\\b ?— ?\\b"," - ",line)
	line = line.replace("’","'").replace("…","...")
	return line

def process_source_file(tts_engine:str, filepath:str, alias2modelname:dict, audios_within_story:list, modelname2queue:dict, audioasset:dict, pause_instead_of_playing_speaker:list, modelname2totaluses:dict, boolvars:dict):
	print("Processing", filepath)
	
	audios_within_story.append([ENUM_START_OF_FILE,0,filepath,""])
	
	lines:list = []
	with open(filepath,"r") as f:
		lines = f.read().split("\n")
	
	parsing_audio_assets:bool = False
	parsing_model_aliases:bool = False
	parsing_model_aliases__active:bool = False
	parsing_note:bool = False
	parsing_htmlcomment:bool = False
	parsing_macro:str = None
	macros:dict = {}
	
	i:int = 0
	while True:
		if i == len(lines):
			break
		line = lines[i]
		line = pre_process_line(line)
		i += 1
		
		if line.startswith("<!--"):
			parsing_htmlcomment = True
		if line.endswith("-->"):
			parsing_htmlcomment = False
			continue
		if parsing_htmlcomment:
			continue
		if line.startswith("<div>"):
			line = line[5:]
		if line.endswith("</div>"):
			line = line[:-6]
		if (line == "") or line.startswith("#"):
			continue
		if line == "== NOTE ==":
			parsing_note = True
			continue
		if parsing_note:
			if line == "== END NOTE ==":
				parsing_note = False
			continue
		if line.startswith("== MACRO="):
			m = re.search("^== MACRO=([^ ]+) ==$", line)
			if m is None:
				raise ValueError(f"Bad macro: {line}")
			parsing_macro = m.group(1)
			macros[parsing_macro] = []
			continue
		if parsing_macro is not None:
			if line == "== END MACRO ==":
				parsing_macro = None
				continue
			macros[parsing_macro].append(line)
			continue
		if line.startswith("MACRO=="):
			try:
				macro_content:list = macros[line[7:]]
			except KeyError:
				raise ValueError(f"Attempting to use unregistered macro: {line}")
			else:
				lines = lines[:i] + macro_content + lines[i:]
			continue
		if line.startswith("IF (PROMPT_FOR_BOOL("):
			promptstr:str = line[len("IF (PROMPT_FOR_BOOL("):-4]
			varstr:str = "PROMPT:"+promptstr
			boolvars[varstr] = getpromptval(promptstr, args.test_audio_volumes)
			audios_within_story.append([ENUM_IFBOOL,0,varstr,""])
			continue
		if line.startswith("IF (CLOCKTIME_MINUS_22 > "):
			m = re.search("^IF \\(CLOCKTIME_MINUS_22 > ([0-9.]+)\\)\\{$", line)
			if m is not None:
				audios_within_story.append([ENUM_IFCLOCKTIMEGT,0,m.group(1),""])
			else:
				raise ValueError(f"Bad IF condition: {line}")
			continue
		if line == "}":
			dealtwith:bool = False
			for start,end in (
				(ENUM_IFCLOCKTIMEGT,ENUM_IFCLOCKTIMEGT_END),
				(ENUM_IFBOOL,ENUM_IFBOOL_END),
			):
				countdiff:int = 0
				for x in audios_within_story:
					countdiff += (x[0] == start) - (x[0] == end)
				if countdiff == 1:
					audios_within_story.append([end,0,"",""])
					dealtwith = True
					break
			if not dealtwith:
				raise ValueError(f"Unknown what scope to close for line {i}: '}}' (NOTE: Line count might be wrong due to macros)")
			continue
		if line == "== AUDIO ASSETS ==":
			parsing_audio_assets = True
			continue
		if parsing_audio_assets:
			if line == "== END AUDIO ASSETS ==":
				parsing_audio_assets = False
				continue
			m = re.search("^([A-Za-z0-9_]+) = (?:volume[*]([0-9]+.[0-9]+) )?(None(?: #.*)?|/.*)$", line)
			if m is not None:
				varname, volume_multiplier_str, fp_and_comment = m.groups()
				if fp_and_comment.startswith("None"):
					if varname in audioasset:
						raise ValueError(f"Overriding audioasset[{varname}] with None")
					audioasset[varname] = (None,0.0)
					continue
				fp:str = strip_trailing_comment(fp_and_comment)
				if not os.path.exists(fp):
					raise ValueError(f"Background audio does not exist: {fp}")
				already_registered:bool = False
				if varname not in audioasset:
					volume_multiplier:float = 1.0
					if volume_multiplier_str is not None:
						volume_multiplier = float(volume_multiplier_str)
					audioasset[varname] = (fp,volume_multiplier)
					print("audioasset[",varname,"] = (",fp,volume_multiplier,")")
				continue
			raise ValueError(f"Bad audio asset line: {line}")
		if line.startswith("== MODEL ALIASES =="):
			if line == "== MODEL ALIASES ==":
				raise ValueError(f"MODEL ALIASES section should be specific to an engine, such as: \"== MODEL ALIASES ==chattts\"")
			parsing_model_aliases = True
			if line in ("== MODEL ALIASES =="+tts_engine, "== MODEL ALIASES ==any"):
				parsing_model_aliases__active = True
			else:
				parsing_model_aliases__active = False
			continue
		if parsing_model_aliases:
			if line == "== END MODEL ALIASES ==":
				parsing_model_aliases = False
				continue
			if parsing_model_aliases__active:
				m = re.search("^([A-Za-z0-9_][A-Za-z0-9_' -]*[A-Za-z0-9_]) *= *(.+)$", line)
				if m is None:
					raise ValueError(f"Bad model alias command line: {line}")
				alias:str = m.group(1)
				modelname:str = strip_trailing_comment(m.group(2))
				if modelname == "PAUSE":
					pause_instead_of_playing_speaker.append(alias)
					continue
				if modelname not in models:
					raise ValueError(f"Not recognised model: {modelname}; possible values: {' '.join([x for x in models])}")
				if alias not in alias2modelname: # Do not override parent aliases
					alias2modelname[alias] = modelname
					modelname2queue[modelname] = []
					modelname2totaluses[modelname] = [0,0]
			continue
		if line.startswith("START__REPEAT_FOR_MINIMUM_OF_N_MINUTES "):
			n_minutes:int = int(line[len("START__REPEAT_FOR_MINIMUM_OF_N_MINUTES "):])
			audios_within_story.append([ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES,0,str(n_minutes),""])
			continue
		if line == "END__REPEAT_FOR_MINIMUM_OF_N_MINUTES":
			audios_within_story.append([ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES,0,"",""])
			continue
		if line == "REPEAT_ALL_FOLLOWING_FOREVER":
			audios_within_story.append([ENUM_REPEAT_UNTIL_ZERO,-1,"",""])
			continue
		if line == "REPEAT_FROM_HERE_IF_ENTER_PRESSED":
			audios_within_story.append([ENUM_torepeatifenterpressed,-1,"",""])
			continue
		if line.startswith("RANDOM_FROM_NUMBERED "):
			rel_file_prefix:str = line[len("RANDOM_FROM_NUMBERED "):]
			filepath_prefix:str = os.path.join(os.path.dirname(filepath), rel_file_prefix)
			filename_prefix:str = os.path.basename(filepath_prefix)
			dirpath:str = os.path.dirname(filepath_prefix)
			options:list = []
			for fname in os.listdir(dirpath):
				if fname.startswith(filename_prefix):
					options.append(fname)
			if len(options) == 0:
				raise ValueError(f"No such files to choose from: {filepath_prefix} ({line})")
			process_source_file(tts_engine, os.path.join(dirpath,random.choice(options)), alias2modelname, audios_within_story, modelname2queue, audioasset, pause_instead_of_playing_speaker, modelname2totaluses, boolvars)
			continue
		m = re.search("^([A-Za-z0-9_][A-Za-z0-9_' -]*[A-Za-z0-9_]): *(.*)$", line)
		if m is not None:
			audios_within_story.append([ENUM_SLEEP,0,delay_between_lines,""])
			
			speaker:str = m.group(1)
			if speaker in pause_instead_of_playing_speaker:
				audios_within_story.append([ENUM_SLEEP,0,"1",""])
				continue
			if speaker not in alias2modelname:
				raise ValueError(f"Not recognised model: {speaker}")
			
			text:str = m.group(2)
			m2 = re.search("^[(][^)]*[)] (.*)$", text)
			if m2 is not None:
				text = m2.group(1)
			m2 = re.search("[^A-Za-z0-9 :;,.?!'\"\u0329-]", text) # NOTE: \u0329 is an invisible character added by ChatGPT for fingerprinting
			if m2 is not None:
				raise ValueError(f"Contains unknown character {m2.group(0)} in {text}")
			
			# piper engine only does sentence gap when capitalised
			text = re.sub(" *[.][.][.] ([a-z])", lambda x:". "+x.group(1).upper(), text)
			
			modelname2totaluses[alias2modelname[speaker]][0] += 1
			modelname2totaluses[alias2modelname[speaker]][1] += len(text)
			
			for subtext in (text,): # re.split(" ?([.][.][.]|[,;:-]) ?", text):
				'''if text == "...":
					audios_within_story.append([ENUM_SLEEP,0,delay_from_dotdotdot,""])
				elif text == ",":
					audios_within_story.append([ENUM_SLEEP,0,delay_from_comma,""])
				elif text == ";":
					audios_within_story.append([ENUM_SLEEP,0,delay_from_semicolon,""])
				elif text == "-":
					audios_within_story.append([ENUM_SLEEP,0,delay_from_dash,""])
				elif text == ":":
					audios_within_story.append([ENUM_SLEEP,0,delay_from_colon,""])
				else:'''
				modelname2queue[alias2modelname[speaker]].append(len(audios_within_story))
				audios_within_story.append([ENUM_VOICE,models[alias2modelname[speaker]][0], subtext,gethashoftext(alias2modelname[speaker],subtext)])
			continue
		m = re.search("^PAUSE ([0-9]+(?:[.][0-9]+)?)s$", line)
		if m is not None:
			audios_within_story.append([ENUM_SLEEP,0,m.group(1),""])
			continue
		m = re.search("^(BG|FG)_AUDIO (.*)$", line)
		if m is not None:
			val:str = strip_trailing_comment(m.group(2))
			if val not in audioasset:
				raise ValueError(f"Not registered as an audio asset: {val} from line {line}")
			if (audioasset[val][0] is None) and (m.group(1) == "FG"): # omit Null foreground audio
				continue
			audios_within_story.append([{"FG":ENUM_FGAUDIO,"BG":ENUM_BGAUDIO}[m.group(1)],0,val,""])
			continue
		if line == "EXIT":
			break
		raise ValueError(f"Bad line: {line}")
	
	for boolvar,errstr in (
		(parsing_audio_assets,"audio"),
		(parsing_model_aliases,"model"),
		(parsing_note,"note"),
		(parsing_htmlcomment,"HTML comment"),
		((parsing_macro is not None),"MACRO"),
	):
		if boolvar:
			raise ValueError(f"Unclosed {errstr} section")
	
	audios_within_story.append([ENUM_END_OF_FILE,0,filepath,""])


if __name__ == "__main__":
	import argparse
	import os
	import re
	
	parser = argparse.ArgumentParser()
	parser.add_argument("inputfile")
	parser.add_argument("--outdir", required=True)
	parser.add_argument("--play", default=False, action="store_true")
	parser.add_argument("--test-audio-volumes", default=False, action="store_true")
	parser.add_argument("--write", default=False, action="store_true")
	parser.add_argument("--remove-unused-audios", default=False, action="store_true")
	parser.add_argument("--stats", default=False, action="store_true")
	parser.add_argument("--no-pause", default=False, action="store_true")
	parser.add_argument("--engine", default="piper")
	parser.add_argument("--settings", required=True, help="/path/to/storyteller-settings.json. See "+os.path.dirname(__file__)+"/settings.example.json for an example")
	args = parser.parse_args()
	
	try:
		import json5 as json
	except ModuleNotFoundError:
		import json
	
	settings_d:dict = None
	with open(args.settings,"r") as f:
		settings_d = json.load(f)
	
	resource_limit:int = settings_d["resource_limit_in_megabytes"]
	if resource_limit != 0:
		''' TODO
		try:
			import psutil
		except ModuleNotFoundError:
			print("WARNING: Resources are not limited. pip install psutil to allow resources to be limited.")
		else:
			virtual_memory = psutil.virtual_memory()
		'''
		
		import resource
		# NOTE: Applying memory limits to avoid system crashing, because some TTS or style-transfer engines assume all computers have 999TB of RAM/VRAM
		# Calculate the maximum memory limit (80% of available memory)
		
		memory_limit = int(resource_limit*1024*1024)
		resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
	
	ctypes.CDLL("/home/vangelic/repos/compsky/__from_chatGPT/playaudio/libcompskyplayaudio.so")
	clib.init_all.restype = ctypes.c_int
	clib.uninit_all.restype = ctypes.c_int
	clib.playAudio.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_float, ctypes.c_float, ctypes.c_float]
	if clib.init_all():
		raise Exception("C library error: init_all() returned true")
	
	run_tts = None
	args.engine = args.engine.lower()
	if args.engine == "piper":
		import ttsengine_piper
		ttsengine_piper.init(settings_d["piper_models"])
		run_tts = ttsengine_piper.run_tts
		models = ttsengine_piper.models
	elif args.engine == "chattts":
		import ttsengine_chattts
		ttsengine_chattts.init(settings_d["chattts_speakers_dir"])
		run_tts = ttsengine_chattts.run_tts
		models = ttsengine_chattts.models
	elif args.engine == "xtts":
		import ttsengine_xtts
		ttsengine_xtts.init(settings_d["xtts_models"])
		run_tts = ttsengine_xtts.run_tts
		models = ttsengine_xtts.models
	else:
		raise ValueError(f"Unrecognised TTS engine: {args.engine}")
	
	if args.outdir[-1] == "/":
		args.outdir = args.outdir[:-1]
	
	if not os.path.exists(args.outdir):
		raise ValueError(f"No such directory: {args.outdir}")
	if not os.path.exists(args.inputfile):
		raise ValueError(f"No such input file: {args.inputfile}")
	
	if not args.outdir.endswith(args.engine):
		raise ValueError(f"Exiting for safety: --outdir does not end in {args.engine}")
	
	alias2modelname:dict = {}
	audios_within_story:list = []
	modelname2queue:dict = {}
	audioasset:dict = {}
	pause_instead_of_playing_speaker:list = []
	modelname2totaluses:dict = {}
	boolvars:dict = {}
	
	process_source_file(args.engine, args.inputfile, alias2modelname, audios_within_story, modelname2queue, audioasset, pause_instead_of_playing_speaker, modelname2totaluses, boolvars)
	
	print("n_lines n_chars")
	for modelname, (n_lines, n_chars) in sorted(modelname2totaluses.items(), key=lambda x:x[1][0]):
		if n_lines != 0:
			print(f"{n_lines:05d}   {n_chars:06d} {modelname}")
	
	all_audio_filepaths:list = [x[3] for x in audios_within_story if x[0]==ENUM_VOICE] + ["libritts399_f67deaf853afabfe410717f10520c816019dbeaf"]
	if args.remove_unused_audios:
		files_to_rm:list = [fname for fname in os.listdir(args.outdir) if fname not in all_audio_filepaths]
		input(f"Removing {len(files_to_rm)} files [Enter to confirm]")
		for fname in files_to_rm:
			os.remove(f"{args.outdir}/{fname}")
	
	audiohash2generationtime:dict = {}
	audiohash2generationtime_fp:str = f"{args.outdir}/_audiohash2generationtime.json"
	if os.path.exists(audiohash2generationtime_fp):
		with open(audiohash2generationtime_fp,"rb") as f:
			audiohash2generationtime = json.loads(gzip_decompress(f.read()))
	deliberately_empty_filepaths:list = []
	for modelname, items in modelname2queue.items():
		if len(items) != 0:
			inputs:list = []
			audio_indices_of_voices:list = [i for i,x in enumerate(audios_within_story) if x[0]==ENUM_VOICE]
			for audioid in items:
				outfile:str = f"{args.outdir}/{audios_within_story[audioid][3]}"
				if not os.path.exists(outfile):
					opts:dict = {
						"text":audios_within_story[audioid][2],
						"output_file":outfile
					}
					if audios_within_story[audioid][1] is not None:
						opts["speaker_id"] = audios_within_story[audioid][1]
					if args.engine != "piper":
						opts["voice_indx"] = audio_indices_of_voices.index(audioid)
					inputs.append(opts)
			if len(inputs) != 0:
				run_tts(args.write, modelname, inputs, args.outdir, audiohash2generationtime, deliberately_empty_filepaths)
	with open(f"{audiohash2generationtime_fp}.new","wb") as f:
		f.write(gzip_compress(json.dumps(audiohash2generationtime).encode()))
	os.rename(f"{audiohash2generationtime_fp}.new",audiohash2generationtime_fp)
	
	if args.stats:
		import contextlib
		import wave
		import json
		fileid2durations:dict = {}
		current_fileids:list = []
		current_fileid:str = None
		stats_output_fp:str = f"{args.outdir}/_stats.json"
		audioid2duration:dict = {}
		if os.path.exists(stats_output_fp):
			with open(stats_output_fp,"rb") as f:
				audioid2duration = json.loads(gzip_decompress(f.read()))
		for audioid in range(len(audios_within_story)):
			item_kind, speakerindx, text, hashoftext = audios_within_story[audioid]
			if item_kind == ENUM_SLEEP:
				fileid2durations[current_fileid][3] += float(text)
			elif item_kind in (ENUM_VOICE,ENUM_FGAUDIO):
				fp:str = None
				if item_kind == ENUM_VOICE:
					fp = "{args.outdir}/{hashoftext}"
				else:
					fp = audioasset[text][0]
					if fp is None:
						print("Ignoring None fp audioasset", text)
						continue
				duration:int = None
				if hashoftext in audioid2duration:
					duration = audioid2duration[hashoftext]
				else:
					if not os.path.exists(fp):
						fileid2durations[current_fileid][1] += 1
						continue
					try:
						with contextlib.closing(wave.open(fp,'rb')) as f:
							frames:int = f.getnframes()
							rate:int = f.getframerate()
							duration:float = frames / float(rate)
							audioid2duration[hashoftext] = duration
					except Exception as e:
						print(f"Error occurred for: {fp}\n\t{e.__class__.__name__}: {e}")
						continue
				fileid2durations[current_fileid][2] += duration
				if item_kind == ENUM_FGAUDIO:
					fileid2durations[current_fileid][4] += duration
			elif item_kind == ENUM_START_OF_FILE:
				current_fileid = text
				current_fileids.append(current_fileid)
				fileid2durations[current_fileid] = [len(current_fileids), 0, 0.0, 0.0, 0.0]
				
				print("START OF FILE",current_fileids)
			elif item_kind == ENUM_END_OF_FILE:
				if current_fileid != text:
					raise ValueError(f"Somehow {current_fileid} == current_fileid != text == {text}\ncurrent_file_ids = {str(current_fileids)}")
				
				print("END OF FILE",current_fileids)
				current_fileids = current_fileids[:-1]
				if len(current_fileids) != 0:
					new_current_fileid:str = current_fileids[-1]
					for i in range(1,4,1):
						fileid2durations[new_current_fileid][i] += fileid2durations[current_fileid][i]
					current_fileid = new_current_fileid
		for hashoftext in list(audioid2duration):
			if hashoftext not in all_audio_filepaths:
				print(f"Deleting stats for audioid2duration[{hashoftext}] == {audioid2duration[hashoftext]}")
				del audioid2duration[hashoftext]
		with open(f"{stats_output_fp}.new","wb") as f:
			f.write(gzip_compress(json.dumps(audioid2duration).encode()))
		if os.path.exists(stats_output_fp):
			os.remove(stats_output_fp)
		os.rename(f"{stats_output_fp}.new", stats_output_fp)
		print("Total audio times from each file:")
		for fileid,vals in sorted(fileid2durations.items(), key=lambda x:x[1][0]):
			indent:str = '  '*(vals[0]-1)
			print(f"{indent}{fileid}\n{indent}* {t2human(vals[2])}\n{indent}* of which {t2human(vals[3])} is sleep and {t2human(vals[4])} is FG_AUDIO\n{indent}* excludes {vals[1]} audios that have yet to be generated")
	
	if args.play or args.test_audio_volumes:
		vlc_binary:str = "vlc" if args.test_audio_volumes else "cvlc"
		from time import sleep
		'''import wave
		import pyaudio
		p = pyaudio.PyAudio()
		for audioid in range(len(audios_within_story)):
			with wave.open(f"{args.outdir}/{audioid}","rb") as wf:
				stream = p.open(
					format=p.get_format_from_width(wf.getsampwidth()),
					channels=wf.getnchannels(),
					rate=wf.getframerate(),
					output=True
				)
				while len(data := wf.readframes(1024)):
					try:
						stream.write(data)
					except SystemError:
						print(f"System error for {args.outdir}/{audioid}")
						raise
				stream.close()
		p.terminate()'''
		
		require_t_greater_than:int = 0
		audioid_of_start_of_t_diff_loop:int = 0
		torepeatifenterpressed_params:list = [0,True,[]]
		audioid:int = 0
		repeat_forever_from:list = [0,True,[]]
		write_ifs:list = []
		write_if:bool = True
		subprocess.Popen(["audio","55"])
		# old_settings = termios.tcgetattr(sys.stdin)
		# tty.setcbreak(sys.stdin.fileno())
		bg_audio_process = None
		prev_played_filepaths:list = []
		while True:
			try:
				while not check_headphones_connected():
					clib.playAudio(b"/media/vangelic/DATA/tmp/tts/libritts399_f67deaf853afabfe410717f10520c816019dbeaf", 0.0, 0.0, 0.1*volume)
				
				if was_key_pressed_since_last_check():
					audioid, write_if, write_ifs = torepeatifenterpressed_params
					if bg_audio_process is not None:
						bg_audio_process.terminate()
						bg_audio_process = None
				elif audioid == len(audios_within_story):
					audioid, write_if, write_ifs = repeat_forever_from
					if bg_audio_process is not None:
						bg_audio_process.terminate()
						bg_audio_process = None
				
				item_kind, speakerindx, text, hashoftext = audios_within_story[audioid]
				
				if args.test_audio_volumes:
					if item_kind not in (ENUM_FGAUDIO,ENUM_BGAUDIO):
						audioid += 1
						continue
				
				if item_kind == ENUM_IFBOOL:
					write_ifs.append(write_if)
					write_if = boolvars[text]
				elif item_kind == ENUM_IFBOOL_END:
					write_if = write_ifs.pop()
				elif item_kind == ENUM_IFCLOCKTIMEGT:
					write_ifs.append(write_if)
					now = dt.now()
					hournow:float = now.hour + now.minute/60
					require_min_hour:float = float(text) + 22.0
					if require_min_hour < 24.0:
						write_if = (hournow >= require_min_hour)
					else:
						write_if = (hournow < 22.0) and (hournow >= (require_min_hour-24.0))
					print(f"{write_if} <- {hournow} vs {require_min_hour}")
				elif item_kind == ENUM_IFCLOCKTIMEGT_END:
					write_if = write_ifs.pop()
				elif (not write_if):
					audioid += 1
					continue
				
				if item_kind == ENUM_SLEEP:
					if not args.no_pause:
						sleep_with_slight_audio(float(text))
						'''if "." in text:
							fp:str = f"{args.outdir}/PAUSE_{text}.ogg"
							if not os.path.exists(fp):
								subprocess.run(["ffmpeg","-f","lavfi","-i","anullsrc","-t",text,"-c:a","libvorbis",fp])
							clib.playAudio(fp.encode())
						else:
							cmds.append(f"vlc://pause:{text}")'''
				elif item_kind == ENUM_VOICE:
					fp:str = f"{args.outdir}/{hashoftext}"
					if fp not in deliberately_empty_filepaths:
						clib.playAudio(fp.encode(), 0.0, 0.0, 0.1*volume) # TODO: normalise volume
					# subprocess.run(["cvlc","--gain",str(volume),"--volume-step","100","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + [fp,"vlc://quit"])
				elif item_kind == ENUM_BGAUDIO:
					if bg_audio_process is not None:
						bg_audio_process.terminate()
					audiometadata:tuple = audioasset[text]
					if audiometadata[0] is None:
						bg_audio_process = None
					else:
						bg_audio_process = set_bg_audio(audiometadata[0], audiometadata[1])
				elif item_kind == ENUM_FGAUDIO:
					audiometadata:tuple = audioasset[text]
					if audiometadata[0] is None:
						print(f"ERROR: audiometadata[{text}] is None")
					else:
						# clib.playAudio(audioasset[text].encode(), 0.0, 0.0)
						# NOTE: --volume-step seems to have no effect
						if (not args.test_audio_volumes) or (audiometadata[0] not in prev_played_filepaths):
							subprocess.run([vlc_binary,"--gain",str(volume*audiometadata[1]),"--volume-step","100","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + [audiometadata[0],"vlc://quit"])
							prev_played_filepaths.append(audiometadata[0])
				elif item_kind == ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES:
					require_t_greater_than = int(dt.now().timestamp()) + 60*int(text)
					audioid_of_start_of_t_diff_loop = audioid
				elif item_kind == ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES:
					t:int = int(dt.now().timestamp())
					print("TODO: Implement ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES")
					#print("Loop due to time minimum requirement?", (t < require_t_greater_than))
					#if t < require_t_greater_than:
					#	audioid = audioid_of_start_of_t_diff_loop # NOTE: Transports to AFTER ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES
				elif item_kind == ENUM_REPEAT_UNTIL_ZERO:
					if audios_within_story[audioid][1] != 0:
						audios_within_story[audioid][1] -= 1
						repeat_forever_from = [audioid, write_if, write_ifs]
				elif item_kind == ENUM_torepeatifenterpressed:
					torepeatifenterpressed_params = [audioid, write_if, write_ifs]
				audioid += 1
			except KeyboardInterrupt:
				raise
				'''if args.test_audio_volumes:
					raise
				s:str = ""
				while True:
					try:
						s = input("Type \"EXIT\" to exit, else it continues from beginning")
					except KeyboardInterrupt:
						pass
					else:
						if s == "EXIT":
							termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
							raise
						else:
							break
				audioid = 0
				write_if = True
				write_ifs = []'''
		
		#for i in range(0,len(cmds)+1,100):
		#	subprocess.run(["cvlc","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + cmds[i:i+100] + ["vlc://quit"])
		
		clib.uninit_all()
