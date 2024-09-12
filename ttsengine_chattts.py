#!/usr/bin/env python3

import os.path
import numpy as np
from datetime import datetime as dt
from ttsengine_utils import combine_inputs

chat = None
torchaudio_save = None
torch_randn = None
torch_from_numpy = None

params_infer_code = {
  'spk_emb': None, # add sampled speaker 
  'temperature': .3, # using custom temperature
  'top_P': 0.7, # top P decode
  'top_K': 20, # top K decode
}

''' Only recognised tokens atm:
uv_break (unvoiced break)
lbreak (long break)
laugh
'''

# use oral_(0-9), laugh_(0-2), break_(0-7) 
# to generate special token in text to synthesize.
params_refine_text = {
  'prompt': '[oral_2][laugh_0][break_6]'
}
# when params_refine_text == '[oral_2][laugh_0][break_6]'
# uv_break can be: breath in, pause

speakerasset_rootdir2allfiles:dict = {}

def init(chattts_speakers_dir:str):
	global speakers_dir
	speakers_dir = chattts_speakers_dir

def sample_random_speaker(mean=None):
	dim = chat.pretrain_models['gpt'].gpt.layers[0].mlp.gate_proj.in_features
	std, _mean = chat.pretrain_models['spk_stat'].chunk(2)
	rand = torch_randn(dim, device=std.device)
	if mean is None:
		mean = _mean
	else:
		rand *= 0.2
	return rand * std + mean

def set_dirs(filepaths:list, rootdir:str):
	path_prefix:str = rootdir+"/"
	for entry in os.listdir(rootdir):
		path:str = path_prefix+entry
		if os.path.isdir(path):
			set_dirs(filepaths, path)
		else:
			filepaths.append(path)

def find_speaker_asset(rootdir:str, name:str):
	name_endswith:str = "/"+name
	allfiles:list = speakerasset_rootdir2allfiles.get(rootdir)
	if allfiles is None:
		allfiles = []
		set_dirs(allfiles, rootdir)
		speakerasset_rootdir2allfiles[rootdir] = allfiles
		print(allfiles)
	asset:str = None
	for fp in allfiles:
		if fp.endswith(name_endswith):
			asset = fp
			break
	return asset

def get_speaker(name:str):
	spk = None
	fp:str = find_speaker_asset(chattts_speakers_dir, name)
	if fp is not None:
		with open(fp,"rb") as f:
			spk = torch_from_numpy(np.load(f))
	else:
		spk = chat.sample_random_speaker()
		with open(f"{chattts_speakers_dir}/{name}","wb") as f:
			np.save(f, spk.detach().numpy())
	return spk

def speak_as(modelname:str, text:str, outfile:str):
	if os.path.exists(outfile):
		return
	params_infer_code["spk_emb"] = get_speaker(modelname)
	wavs = chat.infer(text, params_refine_text=params_refine_text, params_infer_code=params_infer_code)
	torchaudio_save(outfile, torch_from_numpy(wavs[0]), 24000, format="wav")


all_speakers:list = []
set_dirs(all_speakers, chattts_speakers_dir)
models:dict = {fp.split("/")[-1]:[fp] for fp in all_speakers}


def run_tts(is_writeable:bool, modelname:str, jsons:list, outdir:str, audioid2generationtime:dict, deliberately_empty_filepaths:list):
	global chat
	global torchaudio_save
	global torch_randn
	global torch_from_numpy
	
	if (chat is None) and (is_writeable):
		import sys
		sys.path.append("/home/vangelic/repos/ml/ChatTTS/")
		
		try:
			import torchaudio
			import torch
			import ChatTTS
		except ModuleNotFoundError:
			print(f"ERROR: Not in pyenv. Use:  source /path/to/pyenv/tts-chattts/bin/activate")
			raise
		
		chat = ChatTTS.Chat()
		chat.load_models(compile=False) # Set to True for better performance
		torchaudio_save = torchaudio.save
		torch_randn = torch.randn
		torch_from_numpy = torch.from_numpy
	
	prev_t:float = 0.0
	if is_writeable:
		prev_t = dt.now().timestamp()
		params_infer_code["spk_emb"] = get_speaker(modelname)
	
	combined_inputs:list = []
	combine_inputs(combined_inputs, jsons, deliberately_empty_filepaths, 999)
	
	if is_writeable:
		for text, outfile_location in combined_inputs:
			text = text.replace("'","").replace("?"," maybe").replace("!",".") + "[laugh]."
			wavs = chat.infer(text, params_refine_text=params_refine_text, params_infer_code=params_infer_code, lang="en")
			torchaudio_save(outfile_location, torch_from_numpy(wavs[0]), 24000, format="wav")
			if len(wavs) != 1:
				print(f"ERROR: len(wavs) == {len(wavs)} != 1 for {str(wavs)[:100]}... for output of: {text}")
				raise NotImplementedError("Foo bar")
			
			t:float = dt.now().timestamp()
			audioid2generationtime[outfile_location] = t - prev_t
			prev_t = t
