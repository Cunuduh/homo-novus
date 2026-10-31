// Grainy fog over the output circle. It thins step by step, so the figure emerges from it.
const Blob3 = (() => {
  const c = document.getElementById("blob");
  const gl = c.getContext("webgl", { antialias: false, alpha: true, premultipliedAlpha: true });
  const noop = { start() {}, level() {}, stop() {} };
  if (!gl) return noop;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const vs = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
  const fs = `precision highp float;uniform vec2 res;uniform float t,r,o;
  float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,w=.5;for(int i=0;i<4;i++){v+=w*n(p);p=p*2.02+5.3;w*=.5;}return v;}
  void main(){
    vec2 uv=gl_FragCoord.xy/res;vec2 q=(uv-.5)*vec2(res.x/res.y,1.);
    float wob=fbm(q*2.1+vec2(t*.09,-t*.07));
    float wob2=fbm(q*3.4-vec2(t*.05,t*.11)+wob*1.6);
    float edge=max(r,.0001)*(.62+wob*.75);
    float a=1.-smoothstep(edge*.28,edge,length(q));
    if(r<.002)a=0.;
    vec3 deep=vec3(.2,.2,.21),mid=vec3(.47,.47,.47),hot=vec3(.84,.66,.55);
    vec3 col=mix(deep,mid,smoothstep(.25,.65,wob2));
    col=mix(col,hot,smoothstep(.5,.74,wob2)*.85);
    float g=h(gl_FragCoord.xy)-.5;
    col+=g*.2;
    a*=.94+g*.12;
    a=clamp(a,0.,1.)*o;
    gl_FragColor=vec4(clamp(col,0.,1.)*a,a);
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
  const FULL = .78, GROW = 900;
  let raf = 0, mode = "off", t0 = 0, last = 0, op = 1, target = 1;
  const ease = f => f * f * (3 - 2 * f);
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (now - last < 33) return; // 30 fps keeps the GPU free for the model
    last = now;
    const f = now - t0;
    let r = FULL;
    if (mode === "grow") r = FULL * ease(Math.min(f / GROW, 1));
    op += (target - op) * .035;
    if (target === 0 && op < .012) { api.stop(); return; }
    const box = c.getBoundingClientRect(), s = Math.min(1, 640 / Math.max(box.width, box.height));
    const W = Math.max(2, Math.round(box.width * s)), H = Math.max(2, Math.round(box.height * s));
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; gl.viewport(0, 0, W, H); }
    gl.uniform2f(U("res"), W, H); gl.uniform1f(U("t"), still ? 0 : now / 1000); gl.uniform1f(U("r"), r); gl.uniform1f(U("o"), op);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  const api = {
    start() { cancelAnimationFrame(raf); mode = "grow"; t0 = performance.now(); last = 0; op = 1; target = 1; c.hidden = false; raf = requestAnimationFrame(frame); },
    level(v) { target = v; },
    stop() { cancelAnimationFrame(raf); raf = 0; mode = "off"; c.hidden = true; },
  };
  return api;
})();
