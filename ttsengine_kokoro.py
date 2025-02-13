#!/usr/bin/env python3

from kokoro import KPipeline
import spacy
from datetime import datetime as dt
import soundfile
import numpy as np

speed:float = 1.0
sample_rate:int = 24000

models:dict = {name:name for name in "bm_george, bm_fable, af_alloy, af_aoede, af_bella, af_heart, af_jessica, af_kore, af_nicole, af_nova, af_river, af_sarah, af_sky, bf_alice, bf_emma, bf_isabella, bf_lily, ef_dora, ff_siwis, hf_alpha, hf_beta, if_sara, jf_alpha, jf_gongitsune, jf_nezumi, jf_tebukuro, pf_dora, zf_xiaobei, zf_xiaoni, zf_xiaoxiao, zf_xiaoyi".split(", ")}
nlp = spacy.load("xx_ent_wiki_sm")
nlp.add_pipe("sentencizer")
pipeline = KPipeline(lang_code='b') # a=american, b=british, e=spanish, f=french, h=indian, i=italian, j=japanese, p=portuguese, z=chinese # TODO: Allow user to choose

def init(_speakers_dir:str):
	# TODO: Set huggingface downloader cache directory to _speakers_dir?
	pass

def run_tts(is_writeable:bool, modelname:str, jsons:list, outdir:str, audioid2generationtime:dict, deliberately_empty_filepaths:list):
	if not is_writeable:
		return
	
	prev_t:float = dt.now().timestamp()
	for i, entry in enumerate(jsons):
		audio_segments = []
		print(entry["text"])
		for i, sent in enumerate(nlp(entry["text"]).sents):
			for gs, ps, audio in pipeline(sent.text, voice=modelname, speed=speed, split_pattern="\\n"): # TODO: Vary speed
				audio_segments.append(audio)
		outfile_location:str = entry["output_file"]
		soundfile.write(outfile_location, np.concatenate(audio_segments), sample_rate, format="OGG")
		t:float = dt.now().timestamp()
		audioid2generationtime[outfile_location] = t - prev_t
		prev_t = t