from flask import Flask, render_template_string

app = Flask(__name__)

HTML = r"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WEBGHOST — Digital Studio</title>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>

<style>
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
 margin:0;
 background:#000;
 color:#fff;
 font-family:Arial,Tahoma,sans-serif;
 overflow-x:hidden;
}
canvas{
 position:fixed;
 inset:0;
 z-index:-5;
}
.noise{
 position:fixed;
 inset:0;
 z-index:-3;
 pointer-events:none;
 opacity:.035;
 background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
.vignette{
 position:fixed;
 inset:0;
 z-index:-2;
 pointer-events:none;
 background:radial-gradient(circle,transparent 25%,#000 100%);
}
nav{
 position:fixed;
 top:15px;
 left:5%;
 right:5%;
 z-index:99;
 height:64px;
 padding:0 18px;
 display:flex;
 align-items:center;
 justify-content:space-between;
 border:1px solid #ffffff14;
 border-radius:20px;
 background:#050505aa;
 backdrop-filter:blur(25px);
 box-shadow:0 20px 70px #000;
}
.logo{
 font-weight:1000;
 letter-spacing:3px;
 font-size:20px;
}
.logo span{
 color:#8b5cf6;
}
.nav{
 display:flex;
 align-items:center;
 gap:25px;
}
.nav a{
 color:#888;
 text-decoration:none;
 font-size:14px;
 transition:.3s;
}
.nav a:hover{color:#fff}
.lang{
 cursor:pointer;
 border:1px solid #ffffff1c;
 background:#ffffff08;
 color:#fff;
 border-radius:12px;
 padding:9px 14px;
}

/* HERO */

.hero{
 min-height:100vh;
 display:flex;
 justify-content:center;
 align-items:center;
 text-align:center;
 padding:130px 20px 80px;
}
.hero-box{
 max-width:950px;
}
.eyebrow{
 display:inline-flex;
 align-items:center;
 gap:9px;
 border:1px solid #ffffff18;
 background:#ffffff06;
 border-radius:100px;
 padding:9px 15px;
 color:#aaa;
 font-size:12px;
 letter-spacing:1px;
 backdrop-filter:blur(15px);
}
.dot{
 width:7px;
 height:7px;
 border-radius:50%;
 background:#8b5cf6;
 box-shadow:0 0 20px #8b5cf6;
}
h1{
 font-size:clamp(55px,10vw,125px);
 line-height:.88;
 margin:30px 0;
 font-weight:1000;
 letter-spacing:-5px;
}
.gradient{
 background:linear-gradient(
  90deg,#fff,#a78bfa,#6366f1,#fff
 );
 background-size:300%;
 -webkit-background-clip:text;
 color:transparent;
 animation:flow 5s linear infinite;
}
@keyframes flow{
 to{background-position:300%}
}
.hero p{
 color:#777;
 max-width:650px;
 margin:auto;
 line-height:2;
 font-size:17px;
}

/* PREMIUM BUTTONS */

.actions{
 margin-top:40px;
 display:flex;
 justify-content:center;
 flex-wrap:wrap;
 gap:12px;
}
.btn{
 position:relative;
 overflow:hidden;
 display:inline-flex;
 align-items:center;
 justify-content:center;
 gap:10px;
 min-width:170px;
 padding:16px 24px;
 border-radius:16px;
 text-decoration:none;
 color:#fff;
 border:1px solid #ffffff18;
 background:#ffffff06;
 backdrop-filter:blur(15px);
 transition:.35s;
}
.btn:before{
 content:"";
 position:absolute;
 top:0;
 left:-120%;
 width:80%;
 height:100%;
 background:linear-gradient(
  90deg,transparent,#ffffff30,transparent
 );
 transform:skewX(-20deg);
 transition:.6s;
}
.btn:hover:before{left:140%}
.btn:hover{
 transform:translateY(-5px);
 border-color:#ffffff35;
}
.primary{
 background:linear-gradient(135deg,#8b5cf6,#4f46e5);
 border-color:#a78bfa55;
 box-shadow:
 0 15px 60px #7c3aed40,
 inset 0 1px #ffffff66;
}

/* SECTION */

section{
 padding:120px 7%;
}
.section-head{
 text-align:center;
 margin-bottom:60px;
}
.section-head h2{
 font-size:45px;
 margin:0 0 15px;
}
.section-head p{
 color:#666;
}

/* CARDS */

.grid{
 max-width:1150px;
 margin:auto;
 display:grid;
 grid-template-columns:
 repeat(auto-fit,minmax(240px,1fr));
 gap:20px;
}
.card{
 position:relative;
 min-height:270px;
 padding:30px;
 border-radius:28px;
 overflow:hidden;
 border:1px solid #ffffff12;
 background:
 linear-gradient(145deg,#ffffff0a,#ffffff02);
 backdrop-filter:blur(20px);
 box-shadow:0 30px 100px #000;
 transform-style:preserve-3d;
 transition:.5s;
}
.card:hover{
 transform:
 perspective(900px)
 rotateX(5deg)
 rotateY(-5deg)
 translateY(-12px);
 border-color:#8b5cf655;
}
.card:after{
 content:"";
 position:absolute;
 width:180px;
 height:180px;
 right:-90px;
 top:-90px;
 background:#7c3aed;
 opacity:.14;
 filter:blur(70px);
 border-radius:50%;
}
.icon{
 width:58px;
 height:58px;
 display:flex;
 align-items:center;
 justify-content:center;
 border-radius:17px;
 background:#ffffff09;
 border:1px solid #ffffff14;
 font-size:25px;
 margin-bottom:25px;
}
.card h3{
 font-size:22px;
 margin:0 0 12px;
}
.card p{
 color:#777;
 line-height:1.9;
}

/* PROJECT */

.project{
 max-width:1150px;
 margin:auto;
 min-height:330px;
 border-radius:32px;
 border:1px solid #ffffff13;
 background:
 linear-gradient(120deg,#0c0c11,#030305);
 position:relative;
 overflow:hidden;
 display:flex;
 align-items:center;
 padding:50px;
 box-shadow:0 30px 100px #000;
}
.project-glow{
 position:absolute;
 width:350px;
 height:350px;
 right:10%;
 background:#6d28d9;
 opacity:.13;
 filter:blur(100px);
 border-radius:50%;
}
.project-content{
 position:relative;
 z-index:2;
 max-width:600px;
}
.project h2{
 font-size:45px;
 margin-top:0;
}
.project p{
 color:#777;
 line-height:2;
}

/* CTA */

.cta{
 max-width:1000px;
 margin:auto;
 text-align:center;
 padding:90px 25px;
 border-radius:35px;
 border:1px solid #ffffff15;
 background:
 radial-gradient(circle at center,#7c3aed16,transparent 55%),
 #050507;
 box-shadow:0 30px 120px #000;
}
.cta h2{
 font-size:48px;
 margin:0 0 15px;
}
.cta p{
 color:#777;
 margin-bottom:30px;
}

/* FOOTER */

footer{
 padding:60px 20px;
 text-align:center;
 border-top:1px solid #ffffff0d;
 color:#555;
}
footer b{color:#8b5cf6}

/* MOBILE */

@media(max-width:650px){
 nav{
  left:15px;
  right:15px;
 }
 .nav a{display:none}
 h1{
  font-size:57px;
  letter-spacing:-3px;
 }
 .hero p{font-size:15px}
 section{padding:85px 20px}
 .section-head h2,
 .project h2,
 .cta h2{
  font-size:35px;
 }
 .project{
  padding:30px;
 }
}
</style>
</head>

<body>

<div class="noise"></div>
<div class="vignette"></div>

<nav>
 <div class="logo">
  WEB<span>GHOST</span>
 </div>

 <div class="nav">
  <a href="#services"
     data-fa="خدمات"
     data-en="Services">خدمات</a>

  <a href="#projects"
     data-fa="پروژه‌ها"
     data-en="Projects">پروژه‌ها</a>

  <a href="#contact"
     data-fa="ارتباط"
     data-en="Contact">ارتباط</a>

  <button class="lang" onclick="toggleLang()">EN</button>
 </div>
</nav>

<!-- HERO -->

<div class="hero">

 <div class="hero-box">

  <div class="eyebrow">
   <span class="dot"></span>
   <span
    data-fa="استودیو طراحی و توسعه وب"
    data-en="WEB DESIGN & DEVELOPMENT STUDIO">
    استودیو طراحی و توسعه وب
   </span>
  </div>

  <h1>
   <span
    data-fa="ایده‌ات"
    data-en="Your">
    ایده‌ات
   </span>
   <br>

   <span class="gradient"
    data-fa="دیجیتال می‌شود."
    data-en="digitalized.">
    دیجیتال می‌شود.
   </span>
  </h1>

  <p
   data-fa="طراحی و توسعه وب‌سایت‌های مدرن، سریع و اختصاصی برای برندها، کسب‌وکارها و ایده‌های متفاوت."
   data-en="Modern, fast and custom websites for brands, businesses and ambitious ideas.">
   طراحی و توسعه وب‌سایت‌های مدرن، سریع و اختصاصی برای برندها،
   کسب‌وکارها و ایده‌های متفاوت.
  </p>

  <div class="actions">

   <a class="btn primary"
      href="https://t.me/Circus_co"
      target="_blank">

    <span
     data-fa="شروع پروژه"
     data-en="Start Project">
     شروع پروژه
    </span>

    <span>↗</span>
   </a>

   <a class="btn" href="#services">

    <span
     data-fa="خدمات ما"
     data-en="Our Services">
     خدمات ما
    </span>

    <span>↓</span>
   </a>

  </div>

 </div>

</div>

<!-- SERVICES -->

<section id="services">

 <div class="section-head">

  <h2
   data-fa="خدمات WebGhost"
   data-en="WebGhost Services">
   خدمات WebGhost
  </h2>

  <p
   data-fa="از طراحی تا اجرای کامل پروژه."
   data-en="From design to complete development.">
   از طراحی تا اجرای کامل پروژه.
  </p>

 </div>

 <div class="grid">

  <div class="card">
   <div class="icon">✦</div>

   <h3
    data-fa="طراحی سایت"
    data-en="Web Design">
    طراحی سایت
   </h3>

   <p
    data-fa="طراحی رابط‌های مدرن، حرفه‌ای و ریسپانسیو برای هر نوع کسب‌وکار."
    data-en="Modern, premium and responsive interfaces for any business.">
    طراحی رابط‌های مدرن، حرفه‌ای و ریسپانسیو برای هر نوع کسب‌وکار.
   </p>
  </div>

  <div class="card">
   <div class="icon">⌘</div>

   <h3
    data-fa="توسعه وب"
    data-en="Development">
    توسعه وب
   </h3>

   <p
    data-fa="ساخت وب‌سایت‌های سریع، کاربردی و قابل توسعه."
    data-en="Fast, functional and scalable websites.">
    ساخت وب‌سایت‌های سریع، کاربردی و قابل توسعه.
   </p>
  </div>

  <div class="card">
   <div class="icon">◇</div>

   <h3>UI / UX</h3>

   <p
    data-fa="تجربه کاربری ساده، جذاب و حرفه‌ای برای کاربران."
    data-en="Smooth, beautiful and professional user experiences.">
    تجربه کاربری ساده، جذاب و حرفه‌ای برای کاربران.
   </p>
  </div>

  <div class="card">
   <div class="icon">↗</div>

   <h3
    data-fa="فروشگاه آنلاین"
    data-en="E-Commerce">
    فروشگاه آنلاین
   </h3>

   <p
    data-fa="ساخت فروشگاه‌های آنلاین مدرن برای فروش و معرفی محصولات."
    data-en="Modern online stores for selling and showcasing products.">
    ساخت فروشگاه‌های آنلاین مدرن برای فروش و معرفی محصولات.
   </p>
  </div>

 </div>

</section>

<!-- PROJECT -->

<section id="projects">

 <div class="project">

  <div class="project-glow"></div>

  <div class="project-content">

   <h2
    data-fa="پروژه‌ای که در ذهنته؟"
    data-en="Have a project in mind?">
    پروژه‌ای که در ذهنته؟
   </h2>

   <p
    data-fa="ایده‌ات رو به یک تجربه دیجیتال واقعی تبدیل کن. طراحی، توسعه و اجرای پروژه با WebGhost."
    data-en="Turn your idea into a real digital experience. Design, development and delivery by WebGhost.">
    ایده‌ات رو به یک تجربه دیجیتال واقعی تبدیل کن.
    طراحی، توسعه و اجرای پروژه با WebGhost.
   </p>

   <a class="btn primary"
      href="https://t.me/Circus_co"
      target="_blank">

    <span
     data-fa="مشاهده و سفارش"
     data-en="Order Now">
     مشاهده و سفارش
    </span>

    <span>↗</span>

   </a>

  </div>

 </div>

</section>

<!-- CTA -->

<section id="contact">

 <div class="cta">

  <h2
   data-fa="بیایید چیزی متفاوت بسازیم."
   data-en="Let's build something different.">
   بیایید چیزی متفاوت بسازیم.
  </h2>

  <p
   data-fa="برای شروع پروژه یا دریافت اطلاعات بیشتر با ما در ارتباط باشید."
   data-en="Contact us to start your project or get more information.">
   برای شروع پروژه یا دریافت اطلاعات بیشتر با ما در ارتباط باشید.
  </p>

  <a class="btn primary"
     href="https://t.me/Circus_co"
     target="_blank">

   <span
    data-fa="ارتباط با WebGhost"
    data-en="Contact WebGhost">
    ارتباط با WebGhost
   </span>

   <span>↗</span>

  </a>

 </div>

</section>

<footer>
 <b>WebGhost</b> © 2026
 <br><br>
 Code the web. Build the future.
</footer>

<script>

/* LANGUAGE */

let english=false;

function toggleLang(){

 english=!english;

 document.documentElement.lang=
   english ? "en" : "fa";

 document.documentElement.dir=
   english ? "ltr" : "rtl";

 document.querySelector(".lang").textContent=
   english ? "FA" : "EN";

 document.querySelectorAll("[data-fa]").forEach(el=>{
   el.textContent=
     english
       ? el.dataset.en
       : el.dataset.fa;
 });

}

/* THREE.JS */

const scene=new THREE.Scene();

const camera=new THREE.PerspectiveCamera(
 65,
 innerWidth/innerHeight,
 .1,
 1000
);

camera.position.z=7;

const renderer=new THREE.WebGLRenderer({
 alpha:true,
 antialias:true
});

renderer.setPixelRatio(
 Math.min(devicePixelRatio,2)
);

renderer.setSize(
 innerWidth,
 innerHeight
);

document.body.appendChild(renderer.domElement);

/* 3D WIREFRAME */

const geometry=
 new THREE.IcosahedronGeometry(2.25,3);

const material=
 new THREE.MeshBasicMaterial({
  color:0x8b5cf6,
  wireframe:true,
  transparent:true,
  opacity:.12
 });

const orb=
 new THREE.Mesh(
  geometry,
  material
 );

scene.add(orb);

/* INNER CORE */

const coreGeometry=
 new THREE.IcosahedronGeometry(1.3,2);

const coreMaterial=
 new THREE.MeshBasicMaterial({
  color:0x4f46e5,
  wireframe:true,
  transparent:true,
  opacity:.08
 });

const core=
 new THREE.Mesh(
  coreGeometry,
  coreMaterial
 );

scene.add(core);

/* PARTICLES */

const particleGeometry=
 new THREE.BufferGeometry();

const positions=[];

for(let i=0;i<1800;i++){

 positions.push(
  (Math.random()-.5)*40,
  (Math.random()-.5)*40,
  (Math.random()-.5)*40
 );

}

particleGeometry.setAttribute(
 "position",
 new THREE.Float32BufferAttribute(
  positions,3
 )
);

const particleMaterial=
 new THREE.PointsMaterial({
  color:0xffffff,
  size:.022,
  transparent:true,
  opacity:.65
 });

const particles=
 new THREE.Points(
  particleGeometry,
  particleMaterial
 );

scene.add(particles);

/* MOUSE */

let mx=0;
let my=0;

addEventListener("mousemove",e=>{

 mx=(e.clientX/innerWidth-.5);
 my=(e.clientY/innerHeight-.5);

});

/* ANIMATION */

function animate(){

 requestAnimationFrame(animate);

 orb.rotation.x+=.0015;
 orb.rotation.y+=.003;

 core.rotation.x-=.002;
 core.rotation.y-=.003;

 orb.position.x +=
   (mx*1.2-orb.position.x)*.01;

 orb.position.y +=
   (-my*1.2-orb.position.y)*.01;

 particles.rotation.y+=.00025;
 particles.rotation.x+=.00008;

 renderer.render(
  scene,
  camera
 );

}

animate();

/* RESIZE */

addEventListener("resize",()=>{

 camera.aspect=
  innerWidth/innerHeight;

 camera.updateProjectionMatrix();

 renderer.setSize(
  innerWidth,
  innerHeight
 );

});

</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )