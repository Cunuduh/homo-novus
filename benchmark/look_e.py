import subprocess,time,re,pathlib
s=pathlib.Path('parchment_prompt.txt').read_text().strip()
m={'<image5>':'<image1>','<image1>':'<image2>','<image2>':'<image3>','<image3>':'<image4>','<image4>':'<image5>'}
P=re.sub(r'<image\d>',lambda x:m[x.group(0)],s)
for st in ('0.9','0.75'):
    t=time.time()
    r=subprocess.run(['.mflux-venv/bin/mflux-generate-qwen-2.1-edit','--model','qwen-image-2.1-turbo','--image-paths','refs/isolated/pose_vitruvian.jpg','refs/isolated/face_lincoln.jpg','refs/isolated/arms_houdini.jpg','refs/isolated/torso_roosevelt.jpg','refs/isolated/legs_keaton.jpg','--prompt',P,'--seed','42','--quantize','8','--width','1024','--height','1024','--output-resolution','512','--strength',st,'--output',f'benchmark/looks/E_strength_{st}.png'],capture_output=True,text=True)
    print('strength',st,'exit',r.returncode,round(time.time()-t),'s',flush=True)
    if r.returncode: print(r.stderr[-400:])
