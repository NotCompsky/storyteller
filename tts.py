#!/usr/bin/env python3


import subprocess
import json
import hashlib
import random
import zlib
from datetime import datetime as dt

import ctypes
clib = ctypes.CDLL("libcompskyplayaudio.so")
clib.init_all.restype = ctypes.c_int
clib.uninit_all.restype = ctypes.c_int
clib.playAudio.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_float, ctypes.c_float, ctypes.c_float]
if clib.init_all():
	raise Exception("C library error: init_all() returned true")

volume:float = 0.9

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
ENUM_REPEAT_FOREVER:int = 8

models:dict = {
}
for indx in (
	,
):
	models[f"libritts{indx}"] = (indx,"/path/to/piper-voices/en_US-libritts-high.onnx")

def gzip_compress(contents:bytes):
	CO = zlib.compressobj(level=9, wbits=31)
	return CO.compress(contents)+CO.flush()

def gzip_decompress(contents:bytes):
	return zlib.decompress(contents, wbits=31)

def gethashoftext(modelname:str, s:str):
	return modelname + "_" + hashlib.sha1(s.encode()).hexdigest()

def strip_trailing_comment(s:str):
	return re.sub(" *#.*$", "", s)

def run_tts(modelname:str, jsons:list, outdir:str, audioid2generationtime:dict):
	prev_t:float = dt.now().timestamp()
	modelpath:str = models[modelname][1]
	if not os.path.isfile(modelpath):
		raise ValueError(f"No such model: {modelpath}")
	if not os.path.isfile(modelpath+".json"):
		raise ValueError(f"No such model config: {modelpath}.json")
	try:
		p = subprocess.run(["piper","--sentence_silence",delay_between_sentences,"--json-input","--model",modelpath], input="\n".join(jsons), text=True, check=True, capture_output=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	except subprocess.CalledProcessError:
		print(modelname, jsons)
		raise
	else:
		prev_outfile:str = None
		print(p.stderr)
		for line in p.stdout.split("\n"):
			print(line)
			if line.startswith(outdir):
				prev_outfile = line[len(outdir)+1:]
				continue
			m = re.search("\\[(202[0-9]-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]+)\\] \\[piper\\]", line)
			if m is not None:
				t:float = dt.strptime(m.group(1),  "%Y-%m-%d %H:%M:%S.%f").timestamp()
				if re.search("Real-time factor: ([0-9]+[.][0-9]+) [(]infer=", line) is not None:
					audioid2generationtime[prev_outfile] = t - prev_t
				prev_t = t


def process_source_file(filepath:str, alias2modelname:dict, audios_within_story:list, modelname2queue:dict, audioasset:dict, pause_instead_of_playing_speaker:list, modelname2totaluses:dict):
	print("Processing", filepath)
	
	audios_within_story.append((ENUM_START_OF_FILE,0,filepath,""))
	
	lines:list = []
	with open(filepath,"r") as f:
		lines = f.read().split("\n")
	
	parsing_audio_assets:bool = False
	parsing_model_aliases:bool = False
	parsing_note:bool = False
	
	for line in lines:
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
		if line == "== AUDIO ASSETS ==":
			parsing_audio_assets = True
			continue
		if parsing_audio_assets:
			if line == "== END AUDIO ASSETS ==":
				parsing_audio_assets = False
				continue
			m = re.search("^([A-Za-z0-9_]+) = (None(?: #.*)?|/.*)$", line)
			if m is not None:
				if m.group(2).startswith("None"):
					audioasset[m.group(1)] = None
					continue
				fp:str = strip_trailing_comment(m.group(2))
				if not os.path.exists(fp):
					raise ValueError(f"Background audio does not exist: {fp}")
				if m.group(1) not in audioasset:
					audioasset[m.group(1)] = m.group(2)
				continue
			raise ValueError(f"Bad audio asset line: {line}")
		if line == "== MODEL ALIASES ==":
			parsing_model_aliases = True
			continue
		if parsing_model_aliases:
			if line == "== END MODEL ALIASES ==":
				parsing_model_aliases = False
				continue
			m = re.search("^([A-Za-z0-9_][A-Za-z0-9_' ]*[A-Za-z0-9_]) *= *(.+)$", line)
			if m is None:
				raise ValueError(f"Bad model alias command line: {line}")
			alias:str = m.group(1)
			modelname:str = strip_trailing_comment(m.group(2))
			if modelname == "PAUSE":
				pause_instead_of_playing_speaker.append(alias)
				continue
			if modelname not in models:
				raise ValueError(f"Not recognised model: {modelname}")
			if alias not in alias2modelname: # Do not override parent aliases
				alias2modelname[alias] = modelname
				modelname2queue[modelname] = []
				modelname2totaluses[modelname] = [0,0]
			continue
		if line.startswith("START__REPEAT_FOR_MINIMUM_OF_N_MINUTES "):
			n_minutes:int = int(line[len("START__REPEAT_FOR_MINIMUM_OF_N_MINUTES "):])
			audios_within_story.append((ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES,0,str(n_minutes),""))
			continue
		if line == "END__REPEAT_FOR_MINIMUM_OF_N_MINUTES":
			audios_within_story.append((ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES,0,"",""))
			continue
		if line == "REPEAT_ALL_FOLLOWING_FOREVER":
			audios_within_story.append((ENUM_REPEAT_FOREVER,0,"",""))
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
			process_source_file(os.path.join(dirpath,random.choice(options)), alias2modelname, audios_within_story, modelname2queue, audioasset, pause_instead_of_playing_speaker, modelname2totaluses)
			continue
		m = re.search("^([A-Za-z0-9_][A-Za-z0-9_' ]*[A-Za-z0-9_]): *(.*)$", line)
		if m is not None:
			audios_within_story.append((ENUM_SLEEP,0,delay_between_lines,""))
			
			speaker:str = m.group(1)
			if speaker in pause_instead_of_playing_speaker:
				audios_within_story.append((ENUM_SLEEP,0,"1",""))
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
					audios_within_story.append((ENUM_SLEEP,0,delay_from_dotdotdot,""))
				elif text == ",":
					audios_within_story.append((ENUM_SLEEP,0,delay_from_comma,""))
				elif text == ";":
					audios_within_story.append((ENUM_SLEEP,0,delay_from_semicolon,""))
				elif text == "-":
					audios_within_story.append((ENUM_SLEEP,0,delay_from_dash,""))
				elif text == ":":
					audios_within_story.append((ENUM_SLEEP,0,delay_from_colon,""))
				else:'''
				modelname2queue[alias2modelname[speaker]].append(len(audios_within_story))
				audios_within_story.append((ENUM_VOICE,models[alias2modelname[speaker]][0], subtext,gethashoftext(alias2modelname[speaker],subtext)))
			continue
		m = re.search("^PAUSE ([0-9]+(?:[.][0-9]+)?)s$", line)
		if m is not None:
			audios_within_story.append((ENUM_SLEEP,0,m.group(1),""))
			continue
		m = re.search("^(BG|FG)_AUDIO (.*)$", line)
		if m is not None:
			val:str = strip_trailing_comment(m.group(2))
			if val not in audioasset:
				raise ValueError(f"Not registered as an audio asset: {val}")
			if audioasset[val] is None:
				continue
			audios_within_story.append(({"FG":ENUM_FGAUDIO,"BG":ENUM_BGAUDIO}[m.group(1)],0,val,""))
			continue
		if line == "EXIT":
			break
		raise ValueError(f"Bad line: {line}")
	audios_within_story.append((ENUM_END_OF_FILE,0,filepath,""))


if __name__ == "__main__":
	import argparse
	import os
	import re
	
	parser = argparse.ArgumentParser()
	parser.add_argument("inputfile")
	parser.add_argument("--outdir", required=True)
	parser.add_argument("--play", default=False, action="store_true")
	parser.add_argument("--write", default=False, action="store_true")
	parser.add_argument("--remove-unused-audios", default=False, action="store_true")
	parser.add_argument("--stats", default=False, action="store_true")
	args = parser.parse_args()
	
	if args.outdir[-1] == "/":
		args.outdir = args.outdir[:-1]
	
	if not os.path.exists(args.outdir):
		raise ValueError(f"No such directory: {args.outdir}")
	if not os.path.exists(args.inputfile):
		raise ValueError(f"No such input file: {args.inputfile}")
	
	alias2modelname:dict = {}
	audios_within_story:list = []
	modelname2queue:dict = {}
	audioasset:dict = {}
	pause_instead_of_playing_speaker:list = []
	modelname2totaluses:dict = {}
	
	process_source_file(args.inputfile, alias2modelname, audios_within_story, modelname2queue, audioasset, pause_instead_of_playing_speaker, modelname2totaluses)
	
	print("n_lines n_chars")
	for modelname, (n_lines, n_chars) in sorted(modelname2totaluses.items(), key=lambda x:x[1][0]):
		if n_lines != 0:
			print(f"{n_lines:05d}   {n_chars:06d} {modelname}")
	
	all_audio_filepaths:list = [x[3] for x in audios_within_story if x[0]==ENUM_VOICE]
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
	for modelname, items in modelname2queue.items():
		if len(items) != 0:
			if args.write:
				jsons:list = []
				for audioid in items:
					outfile:str = f"{args.outdir}/{audios_within_story[audioid][3]}"
					if not os.path.exists(outfile):
						opts:dict = {
							"text":audios_within_story[audioid][2],
							"output_file":outfile
						}
						if audios_within_story[audioid][1] is not None:
							opts["speaker_id"] = audios_within_story[audioid][1]
						jsons.append(json.dumps(opts))
				if len(jsons) != 0:
					run_tts(modelname, jsons, args.outdir, audiohash2generationtime)
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
			elif item_kind == ENUM_VOICE:
				fp:str = f"{args.outdir}/{hashoftext}"
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
					except Exception:
						print("Error occurred for", fp)
						raise
				fileid2durations[current_fileid][2] += duration
			elif item_kind == ENUM_START_OF_FILE:
				current_fileid = text
				current_fileids.append(current_fileid)
				fileid2durations[current_fileid] = [len(current_fileids), 0, 0.0, 0.0]
				
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
				print(f"Deleting audioid2duration[{hashoftext}] == {audioid2duration[hashoftext]}")
				del audioid2duration[hashoftext]
		with open(f"{stats_output_fp}.new","wb") as f:
			f.write(gzip_compress(json.dumps(audioid2duration).encode()))
		if os.path.exists(stats_output_fp):
			os.remove(stats_output_fp)
		os.rename(f"{stats_output_fp}.new", stats_output_fp)
		print("Total audio times from each file:")
		for fileid,vals in sorted(fileid2durations.items(), key=lambda x:x[1][0]):
			indent:str = '  '*(vals[0]-1)
			print(f"{indent}{fileid}\n{indent}* {vals[2]}s\n{indent}* of which {vals[3]}s is sleep\n{indent}* excludes {vals[1]} audios that have yet to be generated")
	
	if args.play:
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
		audioid:int = 0
		repeat_forever_from:int = 0
		while True:
			if audioid == len(audios_within_story):
				audioid = repeat_forever_from
			
			item_kind, speakerindx, text, hashoftext = audios_within_story[audioid]
			if item_kind == ENUM_SLEEP:
				sleep(float(text))
				'''if "." in text:
					fp:str = f"{args.outdir}/PAUSE_{text}.ogg"
					if not os.path.exists(fp):
						subprocess.run(["ffmpeg","-f","lavfi","-i","anullsrc","-t",text,"-c:a","libvorbis",fp])
					clib.playAudio(fp.encode())
				else:
					cmds.append(f"vlc://pause:{text}")'''
			elif item_kind == ENUM_VOICE:
				fp:str = f"{args.outdir}/{hashoftext}"
				clib.playAudio(fp.encode(), 0.0, 0.0, 0.1*volume) # TODO: normalise volume
				# subprocess.run(["vlc","--gain",str(volume),"--volume-step","100","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + [fp,"vlc://quit"])
			elif item_kind == ENUM_FGAUDIO:
				# clib.playAudio(audioasset[text].encode(), 0.0, 0.0)
				# NOTE: --volume-step seems to have no effect
				subprocess.run(["vlc","--gain",str(volume),"--volume-step","100","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + [audioasset[text],"vlc://quit"])
			elif item_kind == ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES:
				require_t_greater_than = int(dt.now().timestamp()) + 60*int(text)
				audioid_of_start_of_t_diff_loop = audioid
			elif item_kind == ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES:
				t:int = int(dt.now().timestamp())
				print("TODO: Implement ENUM_END_REPEAT_FOR_MINIMUM_OF_N_MINUTES")
				#print("Loop due to time minimum requirement?", (t < require_t_greater_than))
				#if t < require_t_greater_than:
				#	audioid = audioid_of_start_of_t_diff_loop # NOTE: Transports to AFTER ENUM_START_REPEAT_FOR_MINIMUM_OF_N_MINUTES
			elif item_kind == ENUM_REPEAT_FOREVER:
				repeat_forever_from = audioid
			audioid += 1
		
		#for i in range(0,len(cmds)+1,100):
		#	subprocess.run(["vlc","--no-random","--no-video","--no-embedded-video","--no-mouse-events","--no-disable-screensaver","--no-repeat","--no-loop","--audio","--no-fullscreen","--playlist-autostart","--playlist-enqueue"] + cmds[i:i+100] + ["vlc://quit"])
		
		clib.uninit_all()
