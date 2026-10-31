import subprocess,sys,time,pathlib
T=pathlib.Path('direct_prompt.txt').read_text().strip()
base=T.replace(' Sharp realistic photograph, no text.','')
V={
'A_vitruvian_cutout':base.replace('{{SCENE}}','The figure stands frontally in the upper pose of the Vitruvian Man: both arms raised diagonally upward with open hands level with the top of the head, legs apart in a wide stance. The whole figure fits in the frame with space around it. Fully transparent background, with no floor, no shadow and no backdrop. Sharp realistic photograph, no text.'),
'B_oil_romantic':base.replace('{{SCENE}}','The figure stands in a dramatic twisted contrapposto, head turned slightly, one arm reaching upward and one hand hanging heavy, freshly awakened. Behind the figure is a vast stormy Romantic sky over a dark ruined landscape with a low glowing horizon, in the manner of Caspar David Friedrich. A Romantic oil painting with visible brushwork, craquelure and dramatic chiaroscuro, no text.'),
'C_engraving_cutout':base.replace('{{SCENE}}','The figure stands frontally in the upper pose of the Vitruvian Man: both arms raised diagonally upward with open hands level with the top of the head, legs apart in a wide stance. Render as a Renaissance anatomical ink and sepia wash study on aged parchment, with fine cross-hatching, keeping each donor recognizable. No text.'),
}
for n,p in V.items():
    t=time.time()
    r=subprocess.run(['.mflux-venv/bin/mflux-generate-qwen-2.1-edit','--model','qwen-image-2.1-turbo','--image-paths','refs/isolated/face_lincoln.jpg','refs/isolated/arms_houdini.jpg','refs/isolated/torso_roosevelt.jpg','refs/isolated/legs_keaton.jpg','--prompt',p,'--seed','42','--quantize','8','--width','1024','--height','1024','--output-resolution','512','--output',f'benchmark/looks/{n}.png'],capture_output=True,text=True)
    print(n,r.returncode,round(time.time()-t),'s',flush=True)
    if r.returncode: print(r.stderr[-300:])
