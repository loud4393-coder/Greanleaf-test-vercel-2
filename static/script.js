let editing=null;
const $=id=>document.getElementById(id);
async function load(){
 try{
  const r=await fetch("/api/products"); const d=await r.json(); if(!r.ok)throw Error(d.error||r.status);
  $("products").innerHTML="";
  d.products.forEach(p=>{
   const c=document.createElement("article"); c.className="card";
   c.innerHTML=`<h2></h2><div></div><div class="price"></div><button>Редактировать</button><button>Удалить</button>`;
   c.children[0].textContent=p.name;c.children[1].textContent=p.description||"";c.children[2].textContent=`${p.price} ${p.currency}`;
   c.children[3].onclick=()=>edit(p);c.children[4].onclick=()=>remove(p.id);$("products").append(c);
  });
  $("status").textContent=`Каталог загружен: ${d.products.length} товара`;
 }catch(e){$("status").textContent=`Ошибка: ${e.message}`}
}
function edit(p){editing=p.id;$("name").value=p.name;$("price").value=p.price;$("currency").value=p.currency;$("description").value=p.description;$("save").textContent="Сохранить";$("cancel").hidden=false}
$("cancel").onclick=()=>reset();
function reset(){editing=null;$("name").value="";$("price").value="";$("currency").value="TMT";$("description").value="";$("save").textContent="Добавить товар";$("cancel").hidden=true}
$("save").onclick=async()=>{
 const body={name:$("name").value.trim(),price:$("price").value,currency:$("currency").value.trim()||"TMT",description:$("description").value.trim()};
 if(!body.name||body.price===""){ $("msg").textContent="Введите название и цену";return}
 const r=await fetch(editing?`/api/products/${editing}`:"/api/products",{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const d=await r.json(); if(!r.ok){$("msg").textContent=d.error||"Ошибка";return}
 $("msg").textContent=editing?"Изменено":"Добавлено";reset();load();
};
async function remove(id){if(!confirm("Удалить товар?"))return;const r=await fetch(`/api/products/${id}`,{method:"DELETE"});const d=await r.json();$("msg").textContent=d.status==="ok"?"Удалено":(d.error||"Ошибка");load()}
load();
