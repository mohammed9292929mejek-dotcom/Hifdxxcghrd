from flask import Flask, render_template_string

app = Flask(__name__)

HTML = r'''<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WebGhost</title>

<style>
*{box-sizing:border-box}
html{scroll-behavior:smooth}

body{
margin:0;
background:#020204;
color:#fff;
font-family:Tahoma,Arial,sans-serif;
overflow-x:hidden;
}

body:before{
content:"";
position:fixed;
inset:-30%;
z-index:-3;
background:
radial-gradient(circle at 20% 20%,#7c3aed35,transparent 25%),
radial-gradient(circle at 80% 80%,#2563eb25,transparent 25%),
radial-gradient(circle,#9333ea18,transparent 40%);
filter:blur(70px);
animation:bg 10s infinite alternate;
}

@keyframes bg{
from{transform:scale(1) rotate(0)}
to{transform:scale(1.15) rotate(4deg)}
}

.grid{
position:fixed;
inset:0;
z-index:-2;
opacity:.12;
background-image:
linear-gradient(#fff1 1px,transparent 1px),
linear-gradient(90deg,#fff1 1px,transparent 1px);
background-size:55px 55px;
transform:perspective(500px) rotateX(55deg) scale(2);
transform-origin:center bottom;
}

/* NAV */

nav{
position:fixed;
top:15px;
left:4%;
right:4%;
height:65px;
z-index:20;

display:flex;
align-items:center;
justify-content:space-between;

padding:0 20px;

background:#07070bd9;
border:1px solid #ffffff18;
border-radius:20px;

backdrop-filter:blur(20px);

box-shadow:
0 20px 70px #000,
inset 0 1px #ffffff15;
}

.logo{
font-size:21px;
font-weight:900;
letter-spacing:3px;
}

.logo span{color:#9b6cff}

.nav{
display:flex;
align-items:center;
gap:20px;
}

.nav a{
color:#777;
text-decoration:none;
font-size:13px;
}

.nav a:hover{color:#fff}

.lang{
color:white;
background:#ffffff08;
border:1px solid #ffffff18;
padding:9px 15px;
border-radius:12px;
cursor:pointer;
}

/* HERO */

.hero{
min-height:100vh;
display:flex;
align-items:center;
justify-content:center;
text-align:center;
padding:130px 20px 80px;
}

.hero-inner{max-width:950px}

.badge{
display:inline-flex;
gap:9px;
align-items:center;
padding:10px 17px;
border:1px solid #ffffff18;
border-radius:100px;
background:#ffffff06;
color:#888;
font-size:12px;
}

.dot{
width:7px;
height:7px;
border-radius:50%;
background:#9b6cff;
box-shadow:0 0 20px #9b6cff;
}

h1{
font-size:clamp(55px,10vw,125px);
line-height:.85;
letter-spacing:-7px;
margin:35px 0;
font-weight:1000;
}

.gradient{
background:linear-gradient(
90deg,#fff,#c4b5fd,#8b5cf6,#6366f1,#fff
);
background-size:300%;
-webkit-background-clip:text;
color:transparent;
animation:shine 6s linear infinite;
}

@keyframes shine{
to{background-position:300%}
}

.hero p{
color:#777;
line-height:2;
max-width:700px;
margin:auto;
}

.buttons{
display:flex;
justify-content:center;
gap:18px;
flex-wrap:wrap;
margin-top:40px;
}

/* BUTTON */

.btn{
display:inline-flex;
align-items:center;
justify-content:center;
gap:10px;

min-width:180px;
padding:16px 23px;

color:#fff;
text-decoration:none;

background:linear-gradient(145deg,#1c1723,#050507);

border:1px solid #ffffff1c;
border-radius:17px;

box-shadow:
0 8px 0 #14101a,
0 25px 50px #000,
inset 0 1px #ffffff25;

transition:.15s;
transform-style:preserve-3d;
}

.primary{
background:linear-gradient(145deg,#a78bfa,#4c1d95);
box-shadow:
0 8px 0 #32146b,
0 25px 55px #7c3aed55,
inset 0 1px #ffffff66;
}

/* SECTION */

section{
padding:110px 6%;
}

.title{
text-align:center;
margin-bottom:55px;
}

.title h2{
font-size:45px;
margin:0 0 12px;
}

.title p{color:#666}

/* CARDS */

.cards{
max-width:1200px;
margin:auto;

display:grid;
grid-template-columns:
repeat(auto-fit,minmax(250px,1fr));

gap:25px;

perspective:1500px;
}

.card{
position:relative;

min-height:350px;

border-radius:30px;

background:
linear-gradient(145deg,#121218,#030305);

border:1px solid #ffffff14;

box-shadow:
0 35px 90px #000,
inset 0 1px #ffffff0d;

overflow:hidden;

cursor:pointer;

transform-style:preserve-3d;

transition:
transform .22s cubic-bezier(.2,.8,.2,1),
box-shadow .3s,
border .3s;
}

.card:hover{
box-shadow:
0 45px 110px #000,
0 0 50px #7c3aed22;
}

.card.open{
border-color:#9b6cff66;
}

/* LIGHT */

.light{
position:absolute;

width:260px;
height:260px;

border-radius:50%;

background:#8b5cf6;

filter:blur(90px);

opacity:.12;

pointer-events:none;

transition:.2s;
}

/* CONTENT */

.card-main{
position:relative;
z-index:2;
padding:32px;

transform:translateZ(45px);
}

.icon{
width:70px;
height:70px;

display:flex;
align-items:center;
justify-content:center;

font-size:28px;

border-radius:20px;

background:linear-gradient(145deg,#28183e,#070609);

border:1px solid #ffffff20;

box-shadow:
0 10px 0 #0b0710,
0 25px 40px #000,
inset 0 1px #ffffff35;

transition:.2s;
}

.card h3{
font-size:23px;
margin:25px 0 12px;
}

.card p{
color:#777;
line-height:1.9;
}

/*
--------------------------------
پایین کارت
--------------------------------
*/

.open-zone{
position:absolute;
left:0;
right:0;
bottom:0;

height:70px;

display:flex;
align-items:center;
justify-content:center;

z-index:5;

color:#777;

font-size:12px;

background:
linear-gradient(
transparent,
#050507ee
);

transition:.3s;
}

.open-zone span{
padding:9px 15px;

border:1px solid #ffffff12;
border-radius:100px;

background:#ffffff06;

transition:.2s;
}

.card.open .open-zone{
height:55px;
}

.card.open .open-zone span{
transform:rotate(180deg);
}

/*
--------------------------------
DETAILS
--------------------------------
*/

.details{
position:absolute;

left:0;
right:0;
bottom:0;

z-index:4;

padding:28px;

background:
linear-gradient(
180deg,
#08080cfa,
#030305
);

border-top:1px solid #ffffff12;

transform:translateY(105%);

transition:
transform .55s cubic-bezier(.2,.8,.2,1);

box-shadow:0 -25px 60px #000;
}

.card.open .details{
transform:translateY(0);
}

.details h4{
margin:0 0 15px;
font-size:19px;
}

.details p{
font-size:13px;
color:#777;
line-height:1.9;
margin:0 0 18px;
}

.detail-row{
display:grid;
grid-template-columns:1fr 1fr;
gap:10px;
margin-bottom:18px;
}

.info{
padding:12px;

background:#ffffff06;

border:1px solid #ffffff10;
border-radius:13px;
}

.info small{
display:block;
color:#555;
margin-bottom:5px;
}

.info b{
font-size:12px;
}

.details .btn{
width:100%;
min-width:0;
padding:13px;
}

/* PROJECT */

.project{
max-width:1200px;
margin:auto;
padding:65px;

position:relative;
overflow:hidden;

border-radius:40px;

background:linear-gradient(135deg,#100b18,#030305);

border:1px solid #ffffff15;

box-shadow:0 45px 130px #000;
}

.project:after{
content:"";

position:absolute;

width:400px;
height:400px;

right:-150px;
top:-150px;

border-radius:50%;

background:#7c3aed;
filter:blur(100px);

opacity:.14;
}

.project-content{
position:relative;
z-index:2;
max-width:700px;
}

.project h2{
font-size:50px;
margin:0 0 20px;
}

.project p{
color:#777;
line-height:2;
}

/* CTA */

.cta{
max-width:1000px;
margin:auto;

padding:90px 25px;

text-align:center;

border-radius:40px;

background:
radial-gradient(circle,#7c3aed18,transparent 60%),
#050507;

border:1px solid #ffffff15;

box-shadow:0 45px 130px #000;
}

.cta h2{
font-size:48px;
margin:0 0 18px;
}

.cta p{
color:#777;
line-height:2;
}

/* FOOTER */

footer{
padding:65px 20px;
text-align:center;
color:#555;
border-top:1px solid #ffffff0d;
}

footer b{color:#9b6cff}

/* MOBILE */

@media(max-width:650px){

nav{
left:10px;
right:10px;
}

.nav a{display:none}

h1{
font-size:56px;
letter-spacing:-4px;
}

section{
padding:85px 20px;
}

.title h2,
.project h2,
.cta h2{
font-size:35px;
}

.project{
padding:35px 25px;
}

}

/* CLICK ANIMATION */

@keyframes press{
0%{filter:brightness(1)}
50%{filter:brightness(1.5)}
100%{filter:brightness(1)}
}

.pressed{
animation:press .25s ease;
}

</style>
</head>

<body>

<div class="grid"></div>

<nav>

<div class="logo">
WEB<span>GHOST</span>
</div>

<div class="nav">

<a href="#services"
data-fa="خدمات"
data-en="Services">
خدمات
</a>

<a href="#projects"
data-fa="پروژه‌ها"
data-en="Projects">
پروژه‌ها
</a>

<a href="#contact"
data-fa="ارتباط"
data-en="Contact">
ارتباط
</a>

<button class="lang" onclick="toggleLanguage()">EN</button>

</div>

</nav>


<!-- HERO -->

<div class="hero">

<div class="hero-inner">

<div class="badge">

<span class="dot"></span>

<span
data-fa="استودیو طراحی و توسعه وب"
data-en="WEB DESIGN & DEVELOPMENT">
استودیو طراحی و توسعه وب
</span>

</div>

<h1>

<span data-fa="ایده‌ات" data-en="Your">
ایده‌ات
</span>

<br>

<span
class="gradient"
data-fa="دیجیتال می‌شود."
data-en="goes digital.">
دیجیتال می‌شود.
</span>

</h1>

<p
data-fa="طراحی و توسعه وب‌سایت‌های مدرن، سریع و اختصاصی برای برندها و کسب‌وکارها."
data-en="Modern, fast and custom websites for brands and businesses.">

طراحی و توسعه وب‌سایت‌های مدرن،
سریع و اختصاصی برای برندها و کسب‌وکارها.

</p>

<div class="buttons">

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span data-fa="شروع پروژه" data-en="Start Project">
شروع پروژه
</span>

↗

</a>

<a class="btn" href="#services">

<span data-fa="خدمات ما" data-en="Our Services">
خدمات ما
</span>

↓

</a>

</div>

</div>

</div>


<!-- SERVICES -->

<section id="services">

<div class="title">

<h2
data-fa="خدمات WebGhost"
data-en="WebGhost Services">
خدمات WebGhost
</h2>

<p
data-fa="قسمت پایین کارت را بزن تا توضیحات باز شود؛ گوشه‌ها واکنش سه‌بعدی دارند."
data-en="Tap the bottom to open details. Corners have a 3D reaction.">

قسمت پایین کارت را بزن تا توضیحات باز شود؛
گوشه‌ها واکنش سه‌بعدی دارند.

</p>

</div>


<div class="cards">


<!-- CARD 1 -->

<div class="card">

<div class="light"></div>

<div class="card-main">

<div class="icon">✦</div>

<h3
data-fa="طراحی سایت"
data-en="Web Design">
طراحی سایت
</h3>

<p
data-fa="طراحی مدرن و اختصاصی برای وب‌سایت‌های حرفه‌ای."
data-en="Modern custom design for professional websites.">
طراحی مدرن و اختصاصی برای وب‌سایت‌های حرفه‌ای.
</p>

</div>

<div class="open-zone">
<span>⌄</span>
</div>

<div class="details">

<h4
data-fa="طراحی اختصاصی"
data-en="Custom Design">
طراحی اختصاصی
</h4>

<p
data-fa="طراحی ریسپانسیو، مدرن و متناسب با برند شما."
data-en="Responsive, modern design tailored to your brand.">
طراحی ریسپانسیو، مدرن و متناسب با برند شما.
</p>

<div class="detail-row">

<div class="info">
<small>Type</small>
<b>Custom</b>
</div>

<div class="info">
<small>Responsive</small>
<b>100%</b>
</div>

</div>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="سفارش طراحی"
data-en="Order Design">
سفارش طراحی
</span>

↗

</a>

</div>

</div>


<!-- CARD 2 -->

<div class="card">

<div class="light"></div>

<div class="card-main">

<div class="icon">⌘</div>

<h3
data-fa="توسعه وب"
data-en="Web Development">
توسعه وب
</h3>

<p
data-fa="ساخت وب‌اپلیکیشن‌های سریع و قدرتمند."
data-en="Fast and powerful web applications.">
ساخت وب‌اپلیکیشن‌های سریع و قدرتمند.
</p>

</div>

<div class="open-zone">
<span>⌄</span>
</div>

<div class="details">

<h4
data-fa="توسعه حرفه‌ای"
data-en="Professional Development">
توسعه حرفه‌ای
</h4>

<p
data-fa="ساخت پروژه‌های وب با تمرکز روی سرعت و تجربه کاربری."
data-en="Web projects focused on speed and user experience.">
ساخت پروژه‌های وب با تمرکز روی سرعت و تجربه کاربری.
</p>

<div class="detail-row">

<div class="info">
<small>Frontend</small>
<b>HTML / CSS / JS</b>
</div>

<div class="info">
<small>Performance</small>
<b>Optimized</b>
</div>

</div>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="سفارش توسعه"
data-en="Order Development">
سفارش توسعه
</span>

↗

</a>

</div>

</div>


<!-- CARD 3 -->

<div class="card">

<div class="light"></div>

<div class="card-main">

<div class="icon">◇</div>

<h3>UI / UX</h3>

<p
data-fa="رابط کاربری حرفه‌ای و تجربه کاربری روان."
data-en="Premium interfaces and smooth user experiences.">
رابط کاربری حرفه‌ای و تجربه کاربری روان.
</p>

</div>

<div class="open-zone">
<span>⌄</span>
</div>

<div class="details">

<h4>Premium UI / UX</h4>

<p
data-fa="طراحی رابط‌های مدرن با تمرکز روی تجربه کاربری."
data-en="Modern interfaces focused on user experience.">
طراحی رابط‌های مدرن با تمرکز روی تجربه کاربری.
</p>

<div class="detail-row">

<div class="info">
<small>Style</small>
<b>Premium</b>
</div>

<div class="info">
<small>Design</small>
<b>3D</b>
</div>

</div>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="سفارش UI / UX"
data-en="Order UI / UX">
سفارش UI / UX
</span>

↗

</a>

</div>

</div>


<!-- CARD 4 -->

<div class="card">

<div class="light"></div>

<div class="card-main">

<div class="icon">↗</div>

<h3
data-fa="فروشگاه آنلاین"
data-en="E-Commerce">
فروشگاه آنلاین
</h3>

<p
data-fa="فروشگاه مدرن و حرفه‌ای برای کسب‌وکار شما."
data-en="Modern online stores for your business.">
فروشگاه مدرن و حرفه‌ای برای کسب‌وکار شما.
</p>

</div>

<div class="open-zone">
<span>⌄</span>
</div>

<div class="details">

<h4
data-fa="فروشگاه حرفه‌ای"
data-en="Professional Store">
فروشگاه حرفه‌ای
</h4>

<p
data-fa="ساخت فروشگاه آنلاین مدرن و مناسب موبایل."
data-en="Modern mobile-ready online stores.">
ساخت فروشگاه آنلاین مدرن و مناسب موبایل.
</p>

<div class="detail-row">

<div class="info">
<small>Mobile</small>
<b>Ready</b>
</div>

<div class="info">
<small>Design</small>
<b>Premium</b>
</div>

</div>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="ساخت فروشگاه"
data-en="Build Store">
ساخت فروشگاه
</span>

↗

</a>

</div>

</div>

</div>

</section>


<!-- PROJECT -->

<section id="projects">

<div class="project">

<div class="project-content">

<h2
data-fa="ایده‌ات را به محصول تبدیل کن."
data-en="Turn your idea into a product.">
ایده‌ات را به محصول تبدیل کن.
</h2>

<p
data-fa="از یک سایت ساده تا یک پلتفرم کامل، پروژه خود را با WebGhost شروع کنید."
data-en="From a simple website to a complete platform, start with WebGhost.">
از یک سایت ساده تا یک پلتفرم کامل،
پروژه خود را با WebGhost شروع کنید.
</p>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="ثبت سفارش"
data-en="Request Project">
ثبت سفارش
</span>

↗

</a>

</div>

</div>

</section>


<!-- CONTACT -->

<section id="contact">

<div class="cta">

<h2
data-fa="آماده‌ای متفاوت بسازی؟"
data-en="Ready to build different?">
آماده‌ای متفاوت بسازی؟
</h2>

<p
data-fa="برای سفارش طراحی و توسعه سایت با WebGhost در ارتباط باشید."
data-en="Contact WebGhost to start your project.">
برای سفارش طراحی و توسعه سایت با WebGhost در ارتباط باشید.
</p>

<a class="btn primary"
href="https://t.me/Circus_co"
target="_blank">

<span
data-fa="ارتباط با ما"
data-en="Contact Us">
ارتباط با ما
</span>

↗

</a>

</div>

</section>


<footer>

<b>WEBGHOST</b>

<br><br>

Premium Digital Experiences · 2026

</footer>


<script>

/* ==========================
   CARD INTERACTION
========================== */

document.querySelectorAll(".card").forEach(card=>{

const openZone=card.querySelector(".open-zone");
const details=card.querySelector(".details");
const light=card.querySelector(".light");


/*
--------------------------------
پایین کارت = باز شدن توضیحات
--------------------------------
*/

openZone.addEventListener("pointerdown",e=>{

e.stopPropagation();

card.classList.toggle("open");

card.classList.add("pressed");

setTimeout(()=>{
card.classList.remove("pressed");
},250);

});


/*
--------------------------------
گوشه کارت = 3D tilt
--------------------------------
*/

card.addEventListener("pointerdown",e=>{

if(e.target.closest(".open-zone")) return;
if(e.target.closest(".details")) return;

const r=card.getBoundingClientRect();

const x=(e.clientX-r.left)/r.width-.5;
const y=(e.clientY-r.top)/r.height-.5;

const rx=-y*28;
const ry=x*28;

card.style.transition=
"transform .12s cubic-bezier(.2,.8,.2,1)";

card.style.transform=
`perspective(1100px)
rotateX(${rx}deg)
rotateY(${ry}deg)
translateZ(25px)
scale(1.025)`;

if(light){

light.style.transform=
`translate(${x*150}px,${y*150}px)`;

light.style.opacity=".28";

}

setTimeout(()=>{

card.style.transition=
"transform .7s cubic-bezier(.2,.8,.2,1)";

card.style.transform=
"perspective(1100px) rotateX(0deg) rotateY(0deg) translateZ(0) scale(1)";

if(light){
light.style.opacity=".12";
}

},300);

});


/*
--------------------------------
موس = حرکت زنده 3D
--------------------------------
*/

card.addEventListener("pointermove",e=>{

if(e.pointerType==="touch") return;

if(card.classList.contains("open")) return;

const r=card.getBoundingClientRect();

const x=(e.clientX-r.left)/r.width-.5;
const y=(e.clientY-r.top)/r.height-.5;

card.style.transform=
`perspective(1100px)
rotateX(${-y*12}deg)
rotateY(${x*12}deg)
translateY(-7px)`;

if(light){

light.style.transform=
`translate(${x*100}px,${y*100}px)`;

}

});


card.addEventListener("pointerleave",()=>{

card.style.transition=
"transform .6s cubic-bezier(.2,.8,.2,1)";

card.style.transform=
"perspective(1100px) rotateX(0deg) rotateY(0deg) translateY(0)";

});

});


/* ==========================
   BUTTON 3D
========================== */

document.querySelectorAll(".btn").forEach(btn=>{

btn.addEventListener("pointermove",e=>{

if(e.pointerType==="touch")return;

const r=btn.getBoundingClientRect();

const x=(e.clientX-r.left)/r.width-.5;
const y=(e.clientY-r.top)/r.height-.5;

btn.style.transform=
`perspective(600px)
rotateX(${-y*8}deg)
rotateY(${x*8}deg)
translateY(-5px)`;

});

btn.addEventListener("pointerleave",()=>{
btn.style.transform="";
});

});


/* ==========================
   LANGUAGE
========================== */

let english=false;

function toggleLanguage(){

english=!english;

document.documentElement.lang=
english?"en":"fa";

document.documentElement.dir=
english?"ltr":"rtl";

document.querySelector(".lang").textContent=
english?"FA":"EN";

document.querySelectorAll("[data-fa]").forEach(el=>{

el.textContent=
english
?el.dataset.en
:el.dataset.fa;

});

}

</script>

</body>
</html>'''


@app.route("/")
def home():
    return render_template_string(HTML)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
