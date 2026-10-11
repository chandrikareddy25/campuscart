import React, {useEffect, useRef, useState} from 'react';
import { ProductArt, Icon } from './Art';

export default function HeroScene() {
  const host=useRef(null);
  const [ready,setReady]=useState(false);
  const [paused,setPaused]=useState(false);
  const pauseRef=useRef(false);
  useEffect(()=>{pauseRef.current=paused;},[paused]);
  useEffect(()=>{
    if (window.matchMedia('(max-width: 760px)').matches) return;
    let cancelled=false, cleanup=()=>{};
    import('three').then(async THREE=>{
      if(cancelled||!host.current) return;
      const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
      let renderer;
      try {renderer=new THREE.WebGLRenderer({alpha:true,antialias:true});} catch {return;}
      const container=host.current;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.5));
      renderer.outputColorSpace=THREE.SRGBColorSpace;
      container.appendChild(renderer.domElement);
      const scene=new THREE.Scene();
      const camera=new THREE.PerspectiveCamera(35,1,.1,100);
      camera.position.set(0,.3,9);
      scene.add(new THREE.HemisphereLight(0xffffff,0x617993,3));
      const light=new THREE.DirectionalLight(0xffffff,4);light.position.set(-3,5,5);scene.add(light);
      const lime=new THREE.PointLight(0xd1ff7c,20,15);lime.position.set(4,-2,3);scene.add(lime);
      const {RoundedBoxGeometry}=await import('three/addons/geometries/RoundedBoxGeometry.js');
      if(cancelled){renderer.dispose();renderer.domElement.remove();return;}
      const group=new THREE.Group();scene.add(group);
      function rounded(parent,size,pos,color,r=.13){const m=new THREE.Mesh(new RoundedBoxGeometry(...size,4,r),new THREE.MeshStandardMaterial({color,roughness:.5,metalness:.12}));m.position.set(...pos);parent.add(m);return m;}
      const bag=new THREE.Group();group.add(bag);bag.rotation.set(.08,-.4,-.16);bag.position.set(.1,.05,0);
      rounded(bag,[1.65,2.2,.7],[0,0,0],0x354c68,.25);
      rounded(bag,[1.24,.84,.25],[0,-.43,.43],0x24394f,.13);
      rounded(bag,[1.09,.025,.035],[0,-.18,.57],0x8fa2b5,.01);
      rounded(bag,[.4,.16,.03],[0,.42,.37],0xd2ed9e,.03);
      rounded(bag,[.16,.27,.06],[.47,-.28,.59],0xd2ed9e,.03);
      const handle=new THREE.Mesh(new THREE.TorusGeometry(.3,.06,12,32,Math.PI),new THREE.MeshStandardMaterial({color:0x182d42}));handle.position.set(0,1.04,0);bag.add(handle);
      [-.67,.67].forEach(x=>rounded(bag,[.14,1.85,.17],[x,-.1,-.45],0x1c3048,.07));
      const book=new THREE.Group();group.add(book);book.position.set(-1.65,-.72,.4);book.rotation.set(-.2,.35,.18);
      rounded(book,[1.05,1.45,.22],[0,0,0],0xb3c579,.04);rounded(book,[.96,1.32,.18],[.02,0,.035],0xf2e9d7,.02);rounded(book,[1.05,1.45,.035],[0,0,.15],0xb3c579,.01);
      for(let i=0;i<3;i++)rounded(book,[.65-i*.08,.025,.02],[0,.28-i*.12,.178],0x52633c,.005);
      const bottle=new THREE.Group();group.add(bottle);bottle.position.set(1.57,-.55,.3);bottle.rotation.set(.1,.1,.23);
      const bottleMat=new THREE.MeshStandardMaterial({color:0xa4c6b3,roughness:.35,metalness:.3});
      const cylinder=new THREE.Mesh(new THREE.CylinderGeometry(.27,.29,1.3,32),bottleMat);bottle.add(cylinder);
      const cap=new THREE.Mesh(new THREE.CylinderGeometry(.2,.23,.22,32),new THREE.MeshStandardMaterial({color:0x26453e}));cap.position.y=.75;bottle.add(cap);
      const orbit=new THREE.Mesh(new THREE.TorusGeometry(2.5,.008,8,100),new THREE.MeshBasicMaterial({color:0x94a3b8,transparent:true,opacity:.3}));orbit.rotation.set(1.03,.4,.2);group.add(orbit);
      const target={x:0,y:0};
      const move=e=>{const b=container.getBoundingClientRect();target.y=((e.clientX-b.left)/b.width-.5)*.55;target.x=((e.clientY-b.top)/b.height-.5)*.2;};
      const leave=()=>{target.x=0;target.y=0;};
      container.addEventListener('pointermove',move);container.addEventListener('pointerleave',leave);
      const resize=()=>{const {width,height}=container.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();};
      const observer=new ResizeObserver(resize);observer.observe(container);resize();
      let visible=true;const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;});intersection.observe(container);
      let elapsed=0,last=0;
      renderer.setAnimationLoop(t=>{
        const delta=Math.min((t-last)/1000,.05);last=t;
        if(!visible||document.hidden)return;
        if(!pauseRef.current&&!reduced.matches){elapsed+=delta;group.position.y=Math.sin(elapsed*.9)*.09;group.rotation.y+=(target.y-group.rotation.y)*.045;group.rotation.x+=(target.x-group.rotation.x)*.045;book.rotation.z=.18+Math.sin(elapsed*.75)*.04;}
        renderer.render(scene,camera);
      });
      setReady(true);
      cleanup=()=>{renderer.setAnimationLoop(null);observer.disconnect();intersection.disconnect();container.removeEventListener('pointermove',move);container.removeEventListener('pointerleave',leave);scene.traverse(obj=>{obj.geometry?.dispose();if(obj.material)for(const m of Array.isArray(obj.material)?obj.material:[obj.material])m.dispose();});renderer.dispose();renderer.domElement.remove();};
    }).catch(()=>{});
    return ()=>{cancelled=true;cleanup();};
  },[]);
  return <div className="hero-visual"><div className="orbit-label">THE EVERYDAY COLLECTION / 01</div><div className="hero-glow"/><div className="scene" ref={host} aria-hidden="true"/>{!ready&&<div className="scene-fallback"><ProductArt type="bag"/><ProductArt type="book"/></div>}<div className="floating-label label-one"><span className="green-dot"/>Made for the campus commute</div><div className="floating-label label-two"><Icon name="spark" size={16}/> Small essentials. Big possibilities.</div>{ready&&<button className="scene-control" onClick={()=>setPaused(v=>!v)}>{paused?'Play animation':'Pause animation'}</button>}</div>;
}
