#!/usr/bin/env python3


models:dict = {
	,
}
for indx in (
	,
):
	models[f"libritts{indx}"] = (indx,"/path/to/piper-voices/en_US-libritts-high.onnx")



# unused:
def run_tts_and_play(existing_tts_program, speaker_id:int, text:str):
	s:str = "{\"text\":"+json.dumps(text)
	if speaker_id is None:
		s += "}"
	else:
		s += ",\"speaker_id\":"+str(speaker_id)+"}"
	existing_tts_program.stdin.write(json.dumps(s).encode())
	existing_tts_program.stdin.flush()
	output_binary:bytes = b""
	while chunk := text_to_speech_process.stdout.read(chunk_size):
		output_binary += chunk
	aplay_process.stdin.write(output_binary)
	aplay_process.stdin.flush()

def run_tts(is_writeable:bool, modelname:str, jsons:list, outdir:str, audioid2generationtime:dict, deliberately_empty_filepaths:list):
	if not is_writeable:
		return
	
	jsons = [json.dumps(x) for x in jsons]
	
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
