import hashlib

def gethashoftext(modelname:str, s:str):
	return modelname + "_" + hashlib.sha1(s.encode()).hexdigest()
