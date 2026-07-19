// static/script.js
let sepet = [], indirim = 0;

function ac(id) { document.getElementById(id).style.display = 'flex'; }
function kapat(id) { document.getElementById(id).style.display = 'none'; }

function ekle(ad, fiyat) {
    sepet.push({ ad, fiyat });
    guncelle();
    const toast = document.getElementById('toast');
    if (toast) {
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 1500);
    }
}

function sil(i) {
    sepet.splice(i, 1);
    guncelle();
    if (sepet.length > 0) sepetAc();
    else kapat('sepet-modal');
}

function guncelle() {
    let t = sepet.reduce((a, b) => a + b.fiyat, 0);
    let son = t - (t * indirim / 100);
    const sAdet = document.getElementById('s-adet');
    const sToplam = document.getElementById('s-toplam');
    const finalTutar = document.getElementById('final-tutar');
    const cartCount = document.getElementById('cart-count');
    const sepetBar = document.getElementById('sepet-bar');
    if (sAdet) sAdet.innerText = sepet.length;
    if (sToplam) sToplam.innerText = son;
    if (finalTutar) finalTutar.innerText = son;
    if (cartCount) cartCount.innerText = sepet.length;
    if (sepetBar) sepetBar.style.display = sepet.length > 0 ? 'flex' : 'none';
}

function sepetAc() {
    let h = '';
    sepet.forEach((v, i) => {
        h += `<div class="sepet-item"><span>${v.ad}</span><div><b>${v.fiyat} TL</b><span class="sil" onclick="sil(${i})">✕</span></div></div>`;
    });
    const liste = document.getElementById('liste');
    if (liste) liste.innerHTML = h || 'Sepet boş';
    ac('sepet-modal');
}

function kuponUygula() {
    let kod = document.getElementById('kupon-input').value;
    fetch('/kupon-kontrol', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kod: kod })
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            indirim = d.oran;
            alert(`%${d.oran} indirim uygulandı!`);
            guncelle();
        } else {
            alert('Geçersiz kod!');
        }
    });
}

function gonder() {
    let ad = document.getElementById('ad').value.trim();
    let tel = document.getElementById('tel').value.trim();
    let adr = document.getElementById('adr').value.trim();
    if (!ad || !tel || !adr) return alert('Lütfen tüm alanları doldurun!');

    let t = sepet.reduce((a, b) => a + b.fiyat, 0);
    let toplam = t - (t * indirim / 100);

    fetch('/siparis-ver', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            musteri: { ad, tel, adres: adr },
            sepet: sepet,
            toplam: toplam
        })
    })
    .then(r => r.json())
    .then(d => {
        document.getElementById('sid').innerText = '#' + d.id;
        kapat('sepet-modal');
        ac('basari');
        sepet = [];
        indirim = 0;
        guncelle();
    });
}