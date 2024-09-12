def combine_inputs(combined_inputs:list, jsons:list, deliberately_empty_filepaths:list, max_len:int):
	prev_text:str = jsons[0]["text"]
	prev_outfile:str = jsons[0]["output_file"]
	next_desired_indx:int = 0
	for i in range(1,len(jsons),1):
		d = jsons[i]
		if (d["voice_indx"] == next_desired_indx) and (len(prev_text)+len(d["text"])<=max_len):
			prev_text += " ... " + d["text"]
			deliberately_empty_filepaths.append(d["output_file"])
		else:
			combined_inputs.append((prev_text,prev_outfile))
			prev_text = d["text"]
			prev_outfile = d["output_file"]
		next_desired_indx = d["voice_indx"] + 1
	combined_inputs.append((prev_text,prev_outfile))
