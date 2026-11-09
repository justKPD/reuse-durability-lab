import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
export class FixtureView{
 constructor(host){
  this.host=host;this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#eaf0e5');
  this.camera=new THREE.PerspectiveCamera(35,1,.1,100);this.camera.position.set(5,5,6);
  this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.6));this.renderer.shadowMap.enabled=true;host.appendChild(this.renderer.domElement);
  this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.target.set(0,.35,0);this.controls.enableDamping=true;this.controls.minDistance=4;this.controls.maxDistance=13;this.controls.maxPolarAngle=Math.PI*.49;
  this.scene.add(new THREE.HemisphereLight(0xffffff,0x718170,2.5));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(3,8,4);light.castShadow=true;this.scene.add(light);
  const mat=(color,extra={})=>new THREE.MeshStandardMaterial({color,roughness:.48,metalness:.2,...extra});
  const mesh=(geometry,material,x,y,z)=>{const o=new THREE.Mesh(geometry,material);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;this.scene.add(o);return o};
  this.base=mesh(new THREE.BoxGeometry(3.5,.32,2.8),mat('#91a59b'),0,.16,0);
  mesh(new THREE.BoxGeometry(2.7,.6,2.0),mat('#b7c4bc'),0,.59,0);
  this.insert=mesh(new THREE.CylinderGeometry(.52,.52,.75,40),mat('#2c8a82'),0,1.28,0);
  this.seal=mesh(new THREE.TorusGeometry(.65,.055,12,48),mat('#a6b55b'),0,1.05,0);this.seal.rotation.x=Math.PI/2;
  this.cap=mesh(new THREE.BoxGeometry(2.8,.16,2.1),mat('#dde4dc',{transparent:true,opacity:.68}),0,1.7,0);
  this.bolts=[];this.positions=[[-1.0,-.7],[1.0,-.7],[1.0,.7],[-1.0,.7]];
  this.positions.forEach(([x,z])=>{const group=new THREE.Group();const shaft=new THREE.Mesh(new THREE.CylinderGeometry(.08,.08,.8,16),mat('#536c67'));shaft.position.y=-.2;group.add(shaft);const head=new THREE.Mesh(new THREE.CylinderGeometry(.18,.18,.12,6),mat('#347e77'));group.add(head);group.position.set(x,2,z);this.scene.add(group);this.bolts.push(group)});
  const floor=mesh(new THREE.PlaneGeometry(200,200),mat('#eaf0e5',{metalness:0,roughness:1}),0,-.03,0);floor.rotation.x=-Math.PI/2;
  const grid=new THREE.GridHelper(12,24,'#c9d7c6','#dce5d5');grid.position.y=.002;this.scene.add(grid);
  this.arrow=new THREE.ArrowHelper(new THREE.Vector3(0,-1,0),new THREE.Vector3(0,3,0),.85,0x227c76,.22,.14);this.scene.add(this.arrow);
  this.ring=mesh(new THREE.TorusGeometry(.28,.025,8,32),mat('#227c76'),0,1.3,0);this.ring.rotation.x=Math.PI/2;
  this.resize=new ResizeObserver(()=>{const w=host.clientWidth,h=host.clientHeight;this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.updateProjectionMatrix()});this.resize.observe(host);
  this.target=null;this.current={isolated:false,seated:false,seal:false,fasteners:[0,0,0,0]};
  const draw=()=>{this.frame=requestAnimationFrame(draw);this.controls.update();if(this.target)this.animateState();this.renderer.render(this.scene,this.camera)};draw();
 }
 reset(){this.camera.position.set(5,5,6);this.controls.target.set(0,.35,0);this.controls.update()}
 update(step){this.target=step||{after:{isolated:false,seated:false,seal:false,fasteners:[0,0,0,0]},action:{op:'start'},issues:[]}}
 animateState(){const t=this.target,s=t.after;const mix=(o,attr,value)=>{o[attr]+=(value-o[attr])*.13};mix(this.insert.position,'y',s.seated?.86:1.55);mix(this.cap.position,'y',s.seated?1.15:1.8);this.seal.visible=!!s.seal;
  this.bolts.forEach((b,i)=>{const effort=s.fasteners[i]||0;mix(b.position,'y',1.8-effort*.65);b.rotation.y+=Math.abs(b.position.y-(1.8-effort*.65))*.25;const material=b.children[1].material;material.color.set(i===t.action.index?(t.issues.length?'#b64737':'#227c76'):effort?'#849e47':'#63857b')});
  const ix=t.action.op==='fasten'?t.action.index:null;const pos=ix===null?[0,0]:this.positions[ix];this.arrow.position.set(pos[0],2.9,pos[1]);this.arrow.setColor(t.issues.length?0xb64737:0x227c76);this.ring.position.set(pos[0],1.23,pos[1]);this.ring.material.color.set(t.issues.length?'#b64737':'#227c76');
 }
}
