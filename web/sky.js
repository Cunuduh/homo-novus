// Fixed backdrop: a dim oil painting with drifting film grain, brighter around the cursor.
(() => {
  const canvas = document.getElementById("sky");
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, preserveDrawingBuffer: true });
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { x: .5, y: .45, tx: .5, ty: .45, wrath: 0, wrathTarget: 0 };
  window.Sky = { wrath: on => { state.wrathTarget = on ? 1 : 0; if (!on && state.halted) { state.halted = false; requestAnimationFrame(frame); } if (still) state.wrath = state.wrathTarget; } };
  addEventListener("pointermove", e => { state.tx = e.clientX / innerWidth; state.ty = e.clientY / innerHeight; });
  if (!gl) { canvas.style.display = "none"; return; }
  // If the GPU drops the context, fall back to the page's dark background rather than a blank canvas.
  canvas.addEventListener("webglcontextlost", () => { canvas.style.display = "none"; });

  const vs = `attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}`;
  const fs = `precision highp float;
  uniform sampler2D a,b;uniform vec2 res,mouse,sa,sb;uniform float t,wrath;
  float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,w=.5;for(int i=0;i<5;i++){v+=w*n(p);p=p*2.03+7.1;w*=.5;}return v;}
  vec2 cover(vec2 uv,vec2 size,float z){float ar=res.x/res.y,im=size.x/size.y;vec2 s=ar>im?vec2(1.,im/ar):vec2(ar/im,1.);return (uv-.5)*s/z+.5;}
  // Rotates the final colour 90 degrees in OKLCH, holding lightness.
  vec3 toLin(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(.04045,c));}
  vec3 toS(vec3 c){c=clamp(c,0.,1.);return mix(c*12.92,1.055*pow(c,vec3(1./2.4))-.055,step(.0031308,c));}
  float cbrt(float x){return sign(x)*pow(abs(x),1./3.);}
  vec3 shift(vec3 c){c=toLin(clamp(c,0.,1.));
    vec3 l=vec3(dot(c,vec3(.4122,.5363,.0514)),dot(c,vec3(.2119,.6807,.1074)),dot(c,vec3(.0883,.2817,.63)));
    l=vec3(cbrt(l.x),cbrt(l.y),cbrt(l.z));
    float L=dot(l,vec3(.2105,.7936,-.0041)),A=dot(l,vec3(1.978,-2.4286,.4506)),B=dot(l,vec3(.0259,.7828,-.8087));
    float a2=-B,b2=A;
    vec3 m=vec3(L+.3963*a2+.2158*b2,L-.1056*a2-.0639*b2,L-.0895*a2-1.2915*b2);m=m*m*m;
    return toS(vec3(4.0767*m.x-3.3077*m.y+.231*m.z,-1.2684*m.x+2.6098*m.y-.3413*m.z,-.0042*m.x-.7034*m.y+1.7076*m.z));}
  void main(){
    vec2 uv=gl_FragCoord.xy/res;uv.y=1.-uv.y;
    float ar=res.x/res.y;
    float z=1.04+.02*sin(t*.05);
    vec2 smoke=vec2(fbm(uv*3.+t*.015),fbm(uv*3.+9.-t*.012))-.5;
    vec2 w=uv+smoke*.012;
    vec3 ca=texture2D(a,cover(w,sa,z)).rgb,cb=texture2D(b,cover(w,sb,z)).rgb;
    float burn=smoothstep(wrath*1.3-.15,wrath*1.3+.15,fbm(uv*vec2(ar,1.)*2.5)+.15);
    vec3 col=mix(cb,ca,burn);
    float l=length((uv-mouse)*vec2(ar,1.))+(fbm(uv*vec2(ar,1.)*5.+t*.05)-.5)*.14;
    float lamp=smoothstep(.5,.06,l);
    float L=dot(col,vec3(.3,.59,.11));
    float mott=fbm(uv*vec2(ar,1.)*3.2);
    vec3 teal=mix(vec3(.03,.1,.13),vec3(.17,.33,.35),pow(L,.8))*(.6+mott*1.);
    col=mix(teal,col*.8,wrath)+teal*lamp*.22;
    float grain=h(gl_FragCoord.xy)-.5;
    col+=grain*.035+(fbm(uv*vec2(ar,1.)*140.)-.5)*.045;
    gl_FragColor=vec4(shift(col),1.);
  }`;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s)); return s; };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fs));
  gl.bindAttribLocation(prog, 0, "p"); gl.linkProgram(prog); gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const U = n => gl.getUniformLocation(prog, n);
  let loaded = 0;
  const tex = (url, unit, name, sizeU) => {
    const img = new Image();
    img.onload = () => {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
      for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]])
        gl.texParameteri(gl.TEXTURE_2D, k, v);
      gl.uniform1i(U(name), unit); gl.uniform2f(U(sizeU), img.width, img.height);
      if (++loaded === 2) requestAnimationFrame(frame);
    };
    img.src = url;
  };
  tex("assets/abbey.jpg", 0, "a", "sa");
  tex("assets/wrath.jpg", 1, "b", "sb");
  const size = () => {
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(U("res"), canvas.width, canvas.height);
  };
  addEventListener("resize", size); size();
  function frame(ms) {
    state.x += (state.tx - state.x) * .07; state.y += (state.ty - state.y) * .07;
    state.wrath += (state.wrathTarget - state.wrath) * .012;
    gl.uniform2f(U("mouse"), state.x, state.y);
    gl.uniform1f(U("t"), still ? 0 : ms / 1000);
    gl.uniform1f(U("wrath"), state.wrath);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    // Once the transition settles during a run, stop drawing so the GPU is left to the model.
    if (state.wrathTarget === 1 && state.wrath > .97) { state.halted = true; return; }
    requestAnimationFrame(frame);
  }
})();
