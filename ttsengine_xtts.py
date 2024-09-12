#!/usr/bin/env python3

# NOTE: `source /media/vangelic/DATA/repos/TTS/bin/activate  &&  python3 /home/vangelic/repos/compsky/tts/tts-test.py`

from ttsengine_utils import combine_inputs
from datetime import datetime as dt

#modelname:str = "TTSpy_jenny"
# NOTE: Uses ~28.2% RAM at peak, and peak occurs when loading voice encorder model
#tts = TTS.api.TTS("tts_models/en/jenny/jenny")

engine = None

models:dict = {}

def init(d:dict):
	for key,val in d.items():
		models[key] = val

def run_tts(is_writeable:bool, modelname:str, jsons:list, outdir:str, audioid2generationtime:dict, deliberately_empty_filepaths:list):
	global engine
	
	if (engine is None) and is_writeable:
		try:
			import TTS.api # coqui.ai - package is coqui-TTS, derived from mozilla-TTS
		except ModuleNotFoundError:
			print("Run this command:  source /path/to/pyenv/TTS/bin/activate")
			raise
		engine = TTS.api.TTS("tts_models/en/ljspeech/tacotron2-DDC") # NOTE: Uses ~30% RAM at peak
		# Uses LOTS of RAM: tts_models/en/multi-dataset/tortoise-v2
		# Unknown RAM but less than tortoise: tts_models/en/jenny/jenny
	
	combined_inputs:list = []
	combine_inputs(combined_inputs, jsons, deliberately_empty_filepaths, 300)
	
	if modelname == "BM1":
		return # TODO: temporary
	
	prev_t:float = 0.0
	speaker_wav_fp:str = models[modelname]
	if is_writeable:
		prev_t = dt.now().timestamp()
	
	if is_writeable:
		for text, outfile_location in combined_inputs:
			try:
				engine.tts_with_vc_to_file(
					text,
					speaker_wav=speaker_wav_fp,
					file_path=outfile_location
				)
			except (RuntimeError, MemoryError):
				print("MemoryError")
				raise
			t:float = dt.now().timestamp()
			audioid2generationtime[outfile_location] = t - prev_t
			prev_t = t
