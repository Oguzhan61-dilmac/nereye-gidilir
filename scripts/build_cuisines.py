# -*- coding: utf-8 -*-
"""
scripts/build_cuisines.py
Generates data/cuisines.json with rich culinary specialty notes for all 81 Turkish provinces.
"""

import json
import os

CUISINES = {
    "Adana": {
        "dishes": ["🥩 Adana Kebabı", "🍷 Şalgam Suyu", "🍧 Bici Bici", "🥖 Sıkma", "🥟 Taş Kadayıf"],
        "desc": "Zırhla çekilmiş kuzu kıymasının köz ateşinde piştiği tescilli Adana kebabı, yanında acılı buz gibi şalgam ve serinletici gül kokulu bici bici tatlısıyla bir lezzet şölenidir.",
        "tip": "Kebabı lavaşa sarıp közlenmiş biber ve bol sumaklı soğan salatasıyla tatmayı unutmayın."
    },
    "Adıyaman": {
        "dishes": ["🥙 Etsiz Çiğ Köfte", "🍲 Meyir Çorbası", "🥘 Adıyaman Tavası", "🫓 Dövmeç"],
        "desc": "Güneydoğu'nun bereketli topraklarında isotun ve taze yeşilliklerin buluştuğu tescilli çiğ köftesi ve fırında nar gibi kızaran tavası ile damakları fetheder.",
        "tip": "Tarihi çarşıda çiğ köftenin yanında taze lavaş ve ayran istemeyi ihmal etmeyin."
    },
    "Afyonkarahisar": {
        "dishes": ["🥓 Afyon Sucuğu", "🍮 Kaymaklı Ekmek Kadayıfı", "🥐 Haşhaşlı Çörek", "🥩 Ağzıaçık"],
        "desc": "UNESCO tescilli gastronomi şehri Afyon, asırlık baharat harmanıyla hazırlanan sucuğu, manda kaymağı ve şerbetiyle meşhur ekmek kadayıfıyla ünlüdür.",
        "tip": "Manda kaymağının yanında sabah kahvaltısında fırından yeni çıkmış sıcak haşhaşlı bükme mutlaka tadılmalı."
    },
    "Ağrı": {
        "dishes": ["🍖 Abdigör Köftesi", "🍲 Selekeli (Saç Kavurma)", "🥣 Ayranaşı", "🍯 Ağrı Balı"],
        "desc": "İshak Paşa Sarayı eteklerinde asırlardır taş havanlarda dövülerek hazırlanan yağsız ve pamuk gibi Abdigör köftesi, Anadolu'nun en eski diyet yemeği kabul edilir.",
        "tip": "Doğubayazıt manzarasına karşı pişirilen geleneksel kuzu eti selekeli sofraların tacıdır."
    },
    "Aksaray": {
        "dishes": ["🥘 Aksaray Tavası", "🥖 Sıkma", "🧀 Aksaray Tulum Peyniri", "🫓 Şerbetli Pide"],
        "desc": "Ihlara Vadisi'nin eşsiz doğasında kuzu eti ve sarımsakla fırınlanan Aksaray tavası ve yerel hamur işi sıkmasıyla Orta Anadolu'nun en doyurucu lezzet duraklarındandır.",
        "tip": "Köy fırınlarında pişirilen sıcak Aksaray tavası taze pideyle sıyrılarak yenir."
    },
    "Amasya": {
        "dishes": ["🍎 Amasya Elması", "🥐 Amasya Çöreği", "🍲 Baklalı Dolma", "🥣 Toyga Çorbası"],
        "desc": "Yeşilırmak kıyısında yetişen mis kokulu misket elmaları, içi cevizli veya haşhaşlı burma çöreği ve etli baklalı sarma dolmasıyla şehzadeler kentine yakışır bir sofra sunar.",
        "tip": "Tarihi Yalıboyu Evleri manzarasında semaver çayı eşliğinde fırından yeni çıkmış Amasya çöreği yiyin."
    },
    "Ankara": {
        "dishes": ["🥘 Ankara Tavası", "🥯 Ankara Simidi", "🥖 Beypazarı Kurusu", "🥒 Çubuk Turşusu"],
        "desc": "Arpa şehriye ve kuzu incikle fırında ağır ağır demlenen Ankara tavası, bol pekmezli gevrek simidi ve çıtır çıtır meşhur Çubuk turşusuyla başkentin vazgeçilmezidir.",
        "tip": "Ulus'taki tarihi lokantalarda fırından yeni çıkmış sıcak Ankara tavasını denemeden dönmeyin."
    },
    "Antalya": {
        "dishes": ["🥗 Tahinli Antalya Piyazı", "🍢 Antalya Şiş Köfte", "🍦 Yanık Dondurma", "🥣 Hibeş"],
        "desc": "Tarator sosu ve tahinle zenginleştirilen coğrafi işaretli Antalya piyazı, şiş köftesi ve keçi sütünden yapılan karamelize yanık dondurmasıyla Akdeniz'in en özgün lezzetidir.",
        "tip": "Piyazı kuru fasulye gibi değil, ana yemek lezzetinde meşhur şiş köftenin yanında tüketin."
    },
    "Ardahan": {
        "dishes": ["🧀 Ardahan Kaşarı", "🍗 Fırında Kaz Eti", "🥣 Helle Çorbası", "🫓 Feselli"],
        "desc": "Yaylaların zengin çiçek florasıyla olgunlaşan tescilli kaşar peyniri ve kış aylarında kurutulup bulgur pilavı üstünde servis edilen nar gibi kaz etiyle ünlüdür.",
        "tip": "Çıldır Gölü üzerinde kızak turundan sonra fırında demlenmiş kaz etinin tadına bakın."
    },
    "Artvin": {
        "dishes": ["🥮 Laz Böreği", "🥬 Karalahana Sarması", "🥖 Silor", "🌽 Mısır Ekmeği"],
        "desc": "Karadeniz yaylalarının taze tereyağıyla pişen çıtır çıtır şerbetli Laz böreği, yoğurtlu sarımsaklı silor ve kestaneli karalahana sarmasıyla doğanın tüm zenginliğini sofraya taşır.",
        "tip": "Çoruh Nehri kıyısında demli Karadeniz çayı eşliğinde sıcak Laz böreğini mutlaka tadın."
    },
    "Aydın": {
        "dishes": ["🍈 Aydın İnciri", "🍢 Çine Köftesi", "🥧 Paşa Böreği", "🎃 Tahinli Kabak Tatlısı"],
        "desc": "Ege güneşinde kuruyan ballı incirleri, kuzu kıymasının en sade haliyle yoğrulduğu meşhur Çine köftesi ve yufkası et suyuyla ıslatılan asırlık Paşa böreğiyle ünlüdür.",
        "tip": "Çine yolunda mola verip köftenin yanında manda yoğurdu ve tahinli kabak tatlısı ısmarlayın."
    },
    "Balıkesir": {
        "dishes": ["🥪 Susurluk Tostu & Ayranı", "🍮 Höşmerim Tatlısı", "🧀 Ayvalık Cunda Mezeleri", "🥩 Balıkesir Kaymaklısı"],
        "desc": "Mihaliç peynirinin eridiği meşhur Susurluk tostu, köpüklü ayranı ve taze peynir mayasından yapılan altın sarısı höşmerimi ile iki denizin lezzet kavşağıdır.",
        "tip": "Yol üstünde Susurluk tesislerinde bol köpüklü ayran ile çift kaşarlı tost molası verin."
    },
    "Bartın": {
        "dishes": ["🥗 Amasra Salatası", "🥣 Pumpum Çorbası", "🥟 Pirinçli Mantı", "🐟 Taze Mevsim Balığı"],
        "desc": "Karadeniz kıyısındaki Amasra'da en az 25 çeşit taze yeşillik ve sebzeyle sanat eseri gibi süslenen meşhur salatası ve mısır unlu pumpum çorbasıyla tanınır.",
        "tip": "Amasra Kalesi manzaralı balıkçılarda taze tava balığının yanına devasa Amasra salatası söyleyin."
    },
    "Batman": {
        "dishes": ["🥟 Şam Börek", "🥘 Mumbar Dolması", "🍗 Perde Pilavı", "🍢 Batman Kebabı"],
        "desc": "Hasankeyf'in kadim kültüründen süzülen baharatlı kıymalı sac böreği (Şam börek) ve kekik kokulu dağ kuzu etleriyle hazırlanan zengin tencere yemekleriyle ünlüdür.",
        "tip": "Tarihi çarşıdaki fırınlarda odun ateşinde yeni çıkmış çıtır Şam böreğini ayranla deneyin."
    },
    "Bayburt": {
        "dishes": ["🥬 Lor Dolması", "🥣 Tatlı Çorba", "🥧 Su Böreği", "🥘 Galacoş"],
        "desc": "Pazı yapraklarına sarılan taze tulum loru ve bulgurun tereyağıyla fırınlandığı tescilli lor dolması ve kuşburnu marmelatıyla hazırlanan tatlı çorbasıyla özgündür.",
        "tip": "Kış aylarında içinizi ısıtacak sıcak lor dolmasının üzerine bolca eritilmiş tereyağı gezdirin."
    },
    "Bilecik": {
        "dishes": ["🥣 Dağ Eriği Ekşili Çorba", "🍮 Pazaryeri Helvası", "🥟 Büzme Tatlısı", "🍗 Çömlek Kebabı"],
        "desc": "Osmanlı'nın filizlendiği topraklarda yabani dağ erikleriyle mayhoşlaşan çorbası ve Pazaryeri ilçesinin asırlık susam helvasıyla sakin ve derin bir mutfak kültürüne sahiptir.",
        "tip": "Pazaryeri helvacılarında fırınlanmış sıcak helvayı yerel çayla tadın."
    },
    "Bingöl": {
        "dishes": ["🍯 Bingöl Yayla Balı", "🫓 Sorina Pel", "🥣 Mastuva", "🥘 Gömme"],
        "desc": "Yüksek yaylaların endemik çiçeklerinden sağılan ödüllü Bingöl balı, kurutulmuş yufkaların yoğurt ve tereyağıyla buluştuğu Sorina Pel yemeğiyle meşhurdur.",
        "tip": "Sabah kahvaltısında taze köy tereyağının üzerine koyu kıvamlı Bingöl petek balını gezdirin."
    },
    "Bitlis": {
        "dishes": ["🍖 Bitlis Büryan Kebabı", "🍲 Katıklı Dolma", "🥟 Bitlis Köftesi", "🍯 Hizan Balı"],
        "desc": "Sabahın ilk ışıklarında 3 metre derinliğindeki kuyu fırınlarında buharla nar gibi pişen büryan kebabı ve kabak içi dolmasıyla Doğu Anadolu'nun lezzet başkentlerindendir.",
        "tip": "Büryanı geleneksel olarak sabah erkenden, tırnak pide üzerinde kemiksiz isteyerek tüketin."
    },
    "Bolu": {
        "dishes": ["🍚 Mengen Pilavı", "🥩 Abant Kebabı", "🍮 Bolu Beyi Tatlısı", "🥣 Ovmaç Çorbası"],
        "desc": "Osmanlı saray mutfağını yöneten Mengenli aşçıların memleketi Bolu; kuzu etli ve kestaneli pilavları, mantarlı Abant kebabı ve fındıklı tatlılarıyla ünlüdür.",
        "tip": "Mengen'deki geleneksel lokantalarda kuzu etli Mengen pilavını mutlaka deneyin."
    },
    "Burdur": {
        "dishes": ["🍢 Burdur Şiş Köfte", "🥜 Burdur Ceviz Ezmesi", "🥘 Testi Kebabı", "🥣 Kelle Paça"],
        "desc": "Yalnızca dana kıyması ve tuzla yoğrulup pide üzerinde tereyağıyla servis edilen coğrafi işaretli Burdur şişi ve irmiksiz ceviz ezmesiyle damak çatlatan bir sadeliğe sahiptir.",
        "tip": "Yemek sonrası kahvenin yanına taze ceviz ve şekerden dövülerek yapılan Burdur ceviz ezmesini ekleyin."
    },
    "Bursa": {
        "dishes": ["🥩 Bursa İskender Kebabı", "🌰 Kestane Şekeri", "🥧 Bursa Cantığı", "🍮 Kemalpaşa Tatlısı"],
        "desc": "Pide üzerinde incecik döner dilimleri, domates sosu, cızırdayan keçi tereyağı ve tava yoğurduyla efsaneleşen İskender kebabı ve Uludağ kestaneleriyle dünya çapında ünlüdür.",
        "tip": "Tarihi Kayhan Çarşısı'nda fırından yeni çıkmış kıymalı sıcak cantık pidesi yemeden ayrılmayın."
    },
    "Çanakkale": {
        "dishes": ["🧀 Ezine Peyniri", "🍮 Fırınlanmış Peynir Helvası", "🐟 Boğaz Sardalyası", "🍢 Biga Köftesi"],
        "desc": "Kaz Dağları kekikleriyle beslenen koyun ve keçilerin sütünden üretilen Ezine peyniri, taze tuzsuz peynirle fırında üzeri kızartılan peynir helvası ve sardalyasıyla meşhurdur.",
        "tip": "Tarihi çarşıda sıcak fırınlanmış peynir helvasını üzerine dondurma koydurarak tadın."
    },
    "Çankırı": {
        "dishes": ["🥘 Yaren Güveci", "🧂 Çankırı Kaya Tuzu Kavurması", "🥣 İnce Ekmek Muskası", "🍮 Höşmerim"],
        "desc": "Yaren kültürünün bereketiyle toprak çömleklerde saatlerce pişen güveci ve Hititler'den miras kalan 5000 yıllık yer altı tuz mağaralarından çıkan doğal tuzuyla tanınır.",
        "tip": "Kaya tuzu lambalarıyla süslü çarşıda mola verip geleneksel fırın güvecini tadın."
    },
    "Çorum": {
        "dishes": ["🥜 Çorum Leblebisi", "🍚 İskilip Dolması", "🥟 Çorum Kuru Mantısı", "🥧 Çorum Pidesi"],
        "desc": "Bakır kazanlarda odun ateşinde üç kez kavrulan altın rengi leblebileri ve dev kazanlarda bez torbalarda pirincin buharıyla pişen tarihi İskilip cağ dolmasıyla ünlüdür.",
        "tip": "Sıcak taze kavrulmuş tuzlu ve karanfilli leblebilerden paket yaptırmayı unutmayın."
    },
    "Denizli": {
        "dishes": ["🍖 Denizli Fırın Kebabı", "🥤 Zafer Gazozu", "🫘 Çameli Kuru Fasulyesi", "🥣 Kuyu Kebabı"],
        "desc": "Tavlanmış sakız ağacı odununda bakır tavalarda kendi yağıyla pişen nar gibi Denizli fırın kebabı, çatal bıçak kullanılmadan pide üzerinde elle yenmesiyle meşhurdur.",
        "tip": "Tarihi Kaleiçi Demirciler Çarşısı'nda kebabı gramaj usulü sipariş edip buz gibi Zafer gazozuyla için."
    },
    "Diyarbakır": {
        "dishes": ["🍢 Diyarbakır Ciğer Kebabı", "🍮 Burma Kadayıf", "🥘 Meftune", "🧀 Diyarbakır Örgü Peyniri"],
        "desc": "Sabah kahvaltısından gece yarısına kadar közde şişlerde pişen taze kuzu ciğeri, bol cevizli fıstıklı çıtır burma kadayıfı ve sumak ekşili etli meftunesiyle bir lezzet efsanesidir.",
        "tip": "Tarihi Hasan Paşa Hanı'nda zengin serpme kahvaltının ardından Dağkapı'da çıtır burma kadayıf yiyin."
    },
    "Düzce": {
        "dishes": ["🍢 Düzce Köftesi", "🧀 İsli Çerkes Peyniri", "🍚 Konuralp Pirinç Pilavı", "🥘 Çerkes Tavuğu"],
        "desc": "Antik Roma kenti Konuralp'in saraylara layık tarihi pirinci, meşe odununda kurutulan isli Çerkes peyniri ve katkısız dana kıymasından yapılan Düzce köftesiyle ünlüdür.",
        "tip": "Günün yorgunluğunu cevizli nefis Çerkes tavuğu ve tereyağlı Konuralp pilavıyla atın."
    },
    "Edirne": {
        "dishes": ["🥩 Edirne Tava Ciğeri", "🍮 Badem Ezmesi", "🧀 Edirne Beyaz Peyniri", "🥧 Hayrabolu Tatlısı"],
        "desc": "Yaprak gibi incecik doğranıp kızgın yağda saniyeler içinde pişen tescilli tava ciğeri, yanında çıtır acı kurutulmuş Karaağaç biberi ve badem ezmesiyle bir klasik lezzettir.",
        "tip": "Ciğerin yanında servis edilen kızarmış kuru biberi çıtırdatarak yemeyi unutmayın."
    },
    "Elazığ": {
        "dishes": ["🍲 Harput Köftesi", "🍇 Orcik (Cevizli Sucuk)", "🥘 Gömme", "🍦 Vişne Dondurması"],
        "desc": "Harput Kalesi'nin gölgesinde fesleğen kokulu incecik Harput köftesi, Öküzgözü üzümlerinin şırasıyla cevizden yapılan tescilli orcik ve fırın gömmesiyle zengin bir mutfaktır.",
        "tip": "Kapalıçarşı'da ipe dizilmiş taze cevizli orciklerden ve Harput dibek kahvesinden alın."
    },
    "Erzincan": {
        "dishes": ["🧀 Erzincan Şavak Tulum Peyniri", "🥖 Erzincan Ketesi", "🥣 Kemah Ekşili Çorbası", "🍖 Kemah Kavurması"],
        "desc": "Munzur Dağları yaylalarında koyun postunda aylarca olgunlaşan tescilli şavak tulum peyniri, sıcak sac ketesi ve odun fırınında pişen taze lavaşıyla eşsiz bir kahvaltı sunar.",
        "tip": "Tulum peynirini sıcak tandır lavaşının içine bol tereyağıyla sarıp dürüm yapın."
    },
    "Erzurum": {
        "dishes": ["🍢 Erzurum Cağ Kebabı", "🥟 Kadayıf Dolması", "🧀 Erzurum Civil Peyniri", "🥧 Su Böreği"],
        "desc": "Yatık döner şeklinde odun ateşinde pişirilip cağ şişleriyle kesilen nefis kuzu eti cağ kebabı ve içi cevizli çıtır kızarmış şerbetli kadayıf dolmasıyla kış diyarının en sıcak lezzetidir.",
        "tip": "Cağ kebabını doyana kadar şiş şiş isteyin, tatlı faslında ise sıcak kadayıf dolması söyleyin."
    },
    "Eskişehir": {
        "dishes": ["🥟 Çibörek", "🍢 Balaban Köfte", "🍬 Met Helvası", "🥐 Haşhaşlı Çörek"],
        "desc": "Kırım Tatar mutfağının hediyesi olan çıtır çıtır içi sulu kıymalı çibörek, pide üzerinde domates sosu ve yoğurtla sunulan Balaban kebabı ve lif lif ayrılan met helvasıyla meşhurdur.",
        "tip": "Odunpazarı tarihi evleri arasında gezerken sıcak çiböreğin suyunu akıtmadan ilk ısırığı alın."
    },
    "Gaziantep": {
        "dishes": ["Baklava", "🍲 Beyran Çorbası", "🥐 Katmer", "🥩 Alinazik Kebabı", "🍖 Küşleme", "🥣 Yuvalama"],
        "desc": "UNESCO tescilli dünya gastronomi başkenti Gaziantep; sabahın erken saatinde içilen sarımsaklı beyranı, fıstıklı çıtır baklavası ve köz patlıcanlı Alinazik kebabıyla bir lezzet mabedidir.",
        "tip": "Sabah 06:00'da dumanı tüten bir kase beyran ile güne başlayıp ardından çıtır fıstıklı katmer tadın."
    },
    "Giresun": {
        "dishes": ["🌰 Giresun Tombul Fındığı", "🥬 Karalahana Diblesi", "🥧 Fındıklı Tel Kadayıf", "🥣 Çalıçileği Çorbası"],
        "desc": "Dünyanın en kaliteli ve lezzetli tombul fındığının anavatanı Giresun; fındıklı yöresel tatlıları, pirinçli karalahana diblesi ve taze yayla otlarıyla hazırlanan yemekleriyle tanınır.",
        "tip": "Fındık pazarından taze çifte kavrulmuş Giresun fındığı ve fındık ezmesi almadan dönmeyin."
    },
    "Gümüşhane": {
        "dishes": ["🍬 Pestil ve Köme", "🍲 Siron", "🥣 Kuşburnu Çorbası", "🫓 Gümüşhane Ekmeği"],
        "desc": "Dut şırası, süt ve bol fındık/cevizle hazırlanan tescilli pestil ve kömesi, yoğurtlu sarımsaklı fırın yufkası sironu ve C vitamini deposu kuşburnu marmelatıyla ünlüdür.",
        "tip": "Tarihi Süleymaniye Mahallesi'nde cevizli rulo pestil ve taze kuşburnu çayı yudumlayın."
    },
    "Hakkâri": {
        "dishes": ["🍲 Doğaba Çorbası", "🥟 Kıris", "🥘 Kepenir", "🥣 Çorti Aşı"],
        "desc": "Cilo Dağları'nın eteklerinde yoğurt, buğday yarması ve kuzu kıymalı küçük köftelerle saatlerce pişirilen düğün yemeği Doğaba ve dağ pancarlarıyla hazırlanan otantik yemekleriyle zengindir.",
        "tip": "Geleneksel Hakkâri sofrasında taze tandır ekmeğini sıcak Doğaba çorbasına banarak tüketin."
    },
    "Hatay": {
        "dishes": ["🍮 Antakya Künefesi", "🥩 Tepsi & Kağıt Kebabı", "🥣 Humus", "🥟 Oruk (İçli Köfte)", "🧆 Zahter Salatası"],
        "desc": "Medeniyetler şehri ve UNESCO gastronomi kenti Hatay; uzayan tuzsuz peynirli sıcak künefesi, taş fırında pişen kağıt kebabı ve tahinli zeytinyağlı humusuyla benzersizdir.",
        "tip": "Uzun Çarşı kasaplarında kağıt kebabını hazırlatıp hemen fırına verdirin, peşine sıcak künefe yiyin."
    },
    "Iğdır": {
        "dishes": ["🍲 Bozbaş (Piti)", "🥣 Ayranaşı", "🍖 Taş Köfte", "🥧 Kete"],
        "desc": "Ağrı Dağı gölgesinde nohut, safran ve kuzu incikle toprak güveç kaplarında pişirilip lavaş üzerine dökülerek yenen meşhur Piti (Bozbaş) yemeğiyle Kafkas rüzgarları estirir.",
        "tip": "Piti yerken önce suyunu tabağa döküp lavaşı doğrayın, ardından etini ve nohutunu tokmakla ezin."
    },
    "Isparta": {
        "dishes": ["🍖 Isparta Fırın Kebabı", "🌹 Gül Lokumu & Reçeli", "🐟 Sazan Dolması", "🍮 Kabak Tatlısı"],
        "desc": "Gül vadilerinin başkenti Isparta; çalı odunu fırınında saatlerce nar gibi kızaran kuzu tandır kebabı, mis kokulu gül lokumları ve Eğirdir Gölü sazanıyla bilinir.",
        "tip": "Gül hasadı mevsiminde taze gül şerbeti için ve çarşıdaki tarihi kebapçılarda fırın kebabı yiyin."
    },
    "İstanbul": {
        "dishes": ["🐟 Boğaz Balık Ekmek", "🍢 Tarihi Sultanahmet Köftesi", "🥤 Vefa Bozası", "🥐 Sarıyer Böreği", "🥛 Kanlıca Yoğurdu"],
        "desc": "Tarihi yarımadada kömür ızgarasında pişen köftesi, Eminönü'nde taze balık ekmeği, pudra şekerli Kanlıca yoğurdu ve kış gecelerinin vazgeçilmezi leblebili Vefa bozasıyla bir kültür mozaiğidir.",
        "tip": "Eminönü vapur iskelesinde çıtır balık ekmek yedikten sonra tarihi Vefa semtinde boza molası verin."
    },
    "İzmir": {
        "dishes": ["🥯 İzmir Boyozu", "🥪 Çeşme Kumrusu", "🍢 İzmir Köfte", "🍮 Şambali Tatlısı", "🥟 İzmir Bombası"],
        "desc": "Sabahın ilk ışıklarında fırından çıkan fırınlanmış yumurtalı sıcak boyozu, nohut mayalı çıtır kumrusu ve Tarihi Kemeraltı Çarşısı'nın tarçınlı şambali tatlısıyla Ege'nin incisidir.",
        "tip": "Alsancak Kordon'da deniz havası alırken sıcak kumru ve peşine içi akışkan çikolatalı İzmir bombası yiyin."
    },
    "Kahramanmaraş": {
        "dishes": ["🍦 Maraş Dövme Dondurması", "🥩 Eli Böğründe (Yanyana)", "🥣 Maraş Paça Çorbası", "🫓 Maraş Tarhanası"],
        "desc": "Ahir Dağı salebi ve keçi sütüyle satırla kesilecek kıvama getirilen dünyaca ünlü dondurması, fırında kuzu eti ve arpacık soğanla pişen Eli Böğründe tavasıyla efsanedir.",
        "tip": "Tarihi Kapalı Çarşı kasaplarında Eli Böğründe tepsisini fırına sürdürüp dondurmayı çatal bıçakla yiyin."
    },
    "Karabük": {
        "dishes": ["🍬 Safranbolu Lokumu", "🍖 Kuyu Kebabı", "🥟 Safranbolu Bükmesi", "🥧 Peruhi"],
        "desc": "UNESCO mirası Safranbolu'nun gerçek safranla tatlandırılan hafif lokumları, ıspanaklı odun ateşi bükmesi ve süzme yoğurtlu nane kokulu hamur işi Peruhi ile meşhurdur.",
        "tip": "Tarihi konaklar arasında gezerken safranlı lokum eşliğinde közde Türk kahvesi yudumlayın."
    },
    "Karaman": {
        "dishes": ["🥣 Batırık", "🫓 Guymak", "🍗 Fırın Kebabı", "🥣 Arabaşı Çorbası"],
        "desc": "İnce bulgur, menengiç, tahin ve domatesle soğuk çorba kıvamında hazırlanan ferahlatıcı Batırık yemeği ve kış aylarının hamurlu Arabaşı çorbasıyla zengin bir Anadolu mutfağıdır.",
        "tip": "Yaz aylarında Toros esintili Karaman'da buzlu soğuk batırık ile ferahlayın."
    },
    "Kars": {
        "dishes": ["🧀 Kars Kaşarı & Gravyeri", "🍗 Tandırda Kaz Eti", "🥟 Kars Hangeli", "🥖 Kars Ketesi"],
        "desc": "Boğatepe köyünün asırlık İsviçre usulü delikli sarı gravyeri, kışın kurutulup fırınlanan nar gibi kaz eti ve sarımsaklı yoğurtlu hamur yemeği Hangeli ile gastronomi efsanesidir.",
        "tip": "Kars Kalesi eteğindeki tarihi taş mekanlarda fırında pişmiş kaz eti ve bulgur pilavı ziyafeti çekin."
    },
    "Kastamonu": {
        "dishes": ["🥩 Kastamonu Pastırması", "🍬 Çekme Helva", "🥖 Kastamonu Etli Ekmeği", "🌾 Siyez Bulguru Pilavı", "🍗 Banduma"],
        "desc": "Ilgaz Dağları rüzgarında doğal olarak kurutulup satırla incecik doğranan çemensiz pastırması, 10.000 yıllık ata tohumu siyez bulguru ve hindi etli bandumasıyla zengindir.",
        "tip": "Pastırmayı pişirmeden, fırından yeni çıkmış sıcak ekmek arasına koyarak taze tüketin."
    },
    "Kayseri": {
        "dishes": ["🥟 Kayseri Mantısı", "🥩 Kayseri Pastırması & Sucuğu", "🥞 Yağlama (Şebit)", "🍕 Develi Cıvıklısı"],
        "desc": "Bir kaşığa kırk adet sığacak kadar maharetle bükülen yoğurtlu sarımsaklı mantısı, kat kat kıymalı lavaşla sunulan yağlaması ve asırlık çemenli pastırmasıyla lezzet doruğudur.",
        "tip": "Yağlamayı çatal bıçakla değil, katlayarak dörde bölüp elinizle rulo yaparak yiyin."
    },
    "Kilis": {
        "dishes": ["🥘 Kilis Tavası", "🍮 Cennet Çamuru", "🥟 Kilis Oruğu", "🥧 Kilis Katmeri"],
        "desc": "Zırhla kıyılmış kuzu etinin tepsiye yayılıp fırında nar gibi piştiği tescilli Kilis tavası ve bol fıstıklı sıcak kadayıf tatlısı Cennet Çamuru ile damağı mest eder.",
        "tip": "Tarihi Kilis kasaplarında hazırlanan tavanın peşine taze kaymaklı Cennet Çamuru ısmarlayın."
    },
    "Kırıkkale": {
        "dishes": ["🥘 Keskin Tavası", "🥣 Tuvalak Çorbası", "🌱 Madımak Yemeği", "🍖 Kırıkkale Kebabı"],
        "desc": "Keskin ilçesinin kuzu pirzolası, sarımsak ve domatesle güveçte saatlerce pişen meşhur Keskin tavası ve ince bulgurlu köfte çorbası Tuvalak ile tanınır.",
        "tip": "Taş fırında pişen sıcak Keskin tavasını taze tırnak pideyle sıyırarak yiyin."
    },
    "Kırklareli": {
        "dishes": ["🍢 Kırklareli Köftesi", "🍷 Hardaliye", "🧀 Kırklareli Eski Kaşarı", "🥩 Meşe Kömüründe Pirzola"],
        "desc": "Istranca Dağları kekiğiyle beslenen hayvanların etiyle yapılan sulu köftesi, olgunlaşmış eski kaşarı ve üzüm şırasına hardal tohumu eklenerek yapılan asırlık içeceği Hardaliye ile ünlüdür.",
        "tip": "Trakya köftesinin yanında koruyucu içermeyen geleneksel soğuk Hardaliye yudumlayın."
    },
    "Kırşehir": {
        "dishes": ["🍲 Kırşehir Çirlemesi", "🌱 Madımak", "🥘 Çömlek Paça", "🥖 Tandır Ekmeği"],
        "desc": "Ahi Evran kenti Kırşehir; kuru kayısı ve kuzu etinin mükemmel ahengi Çirleme yemeği, kırlardan toplanan taze madımak aşı ve toprak çömlekte pişen paçasıyla bilinir.",
        "tip": "Tarihi Ahi Çarşısı çevresinde tandırda pişmiş kuzu güveci ve yöresel çirlemeyi tadın."
    },
    "Kocaeli": {
        "dishes": ["🍬 İzmit Pişmaniyesi", "🥛 Kandıra Manda Yoğurdu", "🥧 Cızlama", "🍗 Çenesuyu"],
        "desc": "İncecik tel tel dökülen tescilli İzmit pişmaniyesi, serin Karadeniz kıyılarında yetişen mandaların koyu kıvamlı Kandıra yoğurdu ve kestane kebaplarıyla meşhurdur.",
        "tip": "Tarihi dükkanlardan kutu kutu taze kakaolu ve fıstıklı tel pişmaniye almayı ihmal etmeyin."
    },
    "Konya": {
        "dishes": ["🍕 Konya Etliekmeği", "🍖 Fırın Kebabı", "🥣 Bamya Çorbası", "🍬 Mevlana Şekeri", "🥘 Konya Tiridi"],
        "desc": "Mevlana diyarı Konya; bir metre uzunluğunda incecik hamurda pişen etliekmeği, taş fırında saatlerce kendi yağıyla lokum gibi pişen fırın kebabı ve kurutulmuş çiçek bamya çorbasıyla bir destandır.",
        "tip": "Geleneksel Konya düğün pilavı menüsü gibi önce bamya çorbası içip ardından sıcak etliekmek yiyin."
    },
    "Kütahya": {
        "dishes": ["🥣 Sıkıcık Çorbası", "🥟 Cimcik Hamuru", "🥘 Güveç Kebabı", "🥧 Kütahya Höşmerimi"],
        "desc": "Çiniler diyarı Kütahya; incecik hamurların cımbız gibi sıkılmasıyla yapılan tereyağlı Cimcik aşı, tarhana köfteli Sıkıcık çorbası ve toprak güveçte pişen etleriyle bilinir.",
        "tip": "Tarihi Germiyan Sokağı'ndaki konaklarda yoğurtlu sarımsaklı sıcak Cimcik hamuru yiyin."
    },
    "Malatya": {
        "dishes": ["🍑 Malatya Kayısısı", "🍲 Analı Kızlı Çorbası", "🥬 Kiraz Yaprağı Sarması", "🥩 Kağıt Kebabı"],
        "desc": "Dünyanın kayısı ambarı Malatya; erik ekşili kiraz yaprağı köftesi, kıymalı iri köfteyle nohutun harmanlandığı Analı Kızlı yemeği ve fırında pişen kağıt kebabıyla gastronomi cevheridir.",
        "tip": "Şire Pazarı'nda güneşte kurutulmuş gün kurusu kayısı ve kayısı çekirdeği kahvesi tadın."
    },
    "Manisa": {
        "dishes": ["🍢 Manisa Kebabı", "🍬 Mesir Macunu", "🥘 Kula Güveci", "🍢 Akhisar Köftesi"],
        "desc": "Pide üzerinde domates sosu ve eritilmiş tereyağıyla sunulan tescilli Manisa kebabı, 41 çeşit şifalı baharatla hazırlanan asırlık Mesir macunu ve Akhisar köftesiyle meşhurdur.",
        "tip": "Sultan Camii çevresindeki dükkanlardan baharatlı taze Mesir macunu paketleri alın."
    },
    "Mardin": {
        "dishes": ["🍖 Kaburga Dolması", "🥟 Sembusek (Kapalı Lahmacun)", "🥐 Süryani Çöreği", "🥟 İkbebet (Haşlama İçli Köfte)"],
        "desc": "Taş konakların masalsı şehri Mardin; bademli iç pilavla doldurulup saatlerce buharda pişen kaburga dolması, baharatlı kapalı lahmacun Sembusek ve mahlepli Süryani çöreğiyle büyüleyicidir.",
        "tip": "Eski Mardin çarşısında Dibek kahvesi yudumlarken yanında taze mahlepli Süryani çöreği deneyin."
    },
    "Mersin": {
        "dishes": ["🌮 Mersin Tantunisi", "🍮 Kerebiç Tatlısı", "🍬 Cezerye", "🥣 Batırık"],
        "desc": "Pamuk yağıyla sacda cızırdayan incecik dana etiyle hazırlanan coğrafi işaretli tantunisi, çöven otu köpüğüyle sunulan irmikli kerebiç tatlısı ve havuçlu cezeryesiyle Akdeniz'in gözdesidir.",
        "tip": "Tantuniyi açık ekmek (lavaş) içinde bol limon ve acı biber turşusuyla mideye indirin."
    },
    "Muğla": {
        "dishes": ["🥩 Çökertme Kebabı", "🍢 Muğla Köftesi", "🌼 Kabak Çiçeği Dolması", "🍯 Çam Balı"],
        "desc": "Kibrit patates kızartması üzerine ince bonfile dilimleri, sarımsaklı yoğurt ve tereyağlı sosla sunulan Çökertme kebabı, sabah toplanan taze kabak çiçekleri ve çam balıyla Ege zarafetidir.",
        "tip": "Bodrum veya Akyaka sahillerinde gün batımında zeytinyağlı ılık kabak çiçeği dolması yiyin."
    },
    "Muş": {
        "dishes": ["🥟 Muş Köftesi", "🥧 Heft Kat Tatlısı", "🥣 Çorti Aşı", "🧀 Muş Kaşarı"],
        "desc": "Muş Ovası'nın etli ve bulgurlu lezzet geleneğini yansıtan dev haşlama Muş köftesi ve lahana turşusunun buğdayla kaynatıldığı geleneksel ekşili Çorti aşıyla tanınır.",
        "tip": "Kış soğuğunda içinizi ısıtacak taze kaynatılmış ekşi Çorti aşı ve sıcak tandır ekmeği deneyin."
    },
    "Nevşehir": {
        "dishes": ["🥘 Kapadokya Testi Kebabı", "🥘 Nevşehir Tavası", "🍇 Üzüm Pekmezi", "🎃 Sütlü Kabak Çekirdeği"],
        "desc": "Avanos'un kızıl toprak çömleklerinde kuzu eti ve sebzelerle mühürlenip alev alev masada kırılan Testi kebabı ve Kapadokya bağlarının meşhur üzümleriyle bir gastronomi şölenidir.",
        "tip": "Testi kebabını sipariş edip masanızda özel satırla testi kırma seremonisini izleyin."
    },
    "Niğde": {
        "dishes": ["🥘 Niğde Tavası", "🍏 Niğde Elması", "🥖 Patatesli Ekmek", "🥣 Mangır Çorbası"],
        "desc": "Aladağlar'ın yaylalarında yetişen kuzu eti, sarımsak ve biberle fırınlanan tescilli Niğde tavası, bol patatesli köy ekmeği ve sulu misket elmalarıyla bilinir.",
        "tip": "Niğde çarşısında taş fırından yeni çıkmış sıcak Niğde tavasını pideyle sıyırarak yiyin."
    },
    "Ordu": {
        "dishes": ["🍕 Ordu Yağlı Pidesi", "🌰 Ordu Fındığı", "🥬 Pancar Diblesi", "🌱 Melocan Kavurması"],
        "desc": "Gevrek hamuru, ortasında eriyen yerel peyniri ve üzerine kırılan taze köy yumurtasıyla meşhur Ordu yağlı pidesi ve orman diplerinden toplanan melocan kavurmasıyla lezizdir.",
        "tip": "Boztepe teleferiğine binmeden önce sahil boyundaki pidecilerde bol tereyağlı Ordu pidesi yiyin."
    },
    "Osmaniye": {
        "dishes": ["🥜 Osmaniye Yer Fıstığı", "🥣 Tirşik Çorbası (Andırın Doktoru)", "🍲 Toğga Çorbası", "🥟 Kömbe"],
        "desc": "Türkiye'nin tescilli yer fıstığı başkenti Osmaniye; yabani pancarla mayalanıp kış aylarında şifa kaynağı sayılan ekşi Tirşik çorbası ve fıstıklı yöresel tatlılarıyla ünlüdür.",
        "tip": "Kavrulmuş sıcak taze Osmaniye fıstığı ve fıstık ezmesi paketlerinden mutlaka edinin."
    },
    "Rize": {
        "dishes": ["🫕 Rize Muhlaması (Mıhlama)", "☕ Rize Çayı", "🥩 Rize Kavurması", "🥮 Laz Böreği", "🍇 Pepeçura"],
        "desc": "Mısır unu, tel peyniri ve yayık tereyağının uzayıp giden dansı meşhur Muhlama, dünyaca ünlü taze demli Rize çayı ve siyah kokulu üzümden yapılan mor Pepeçura tatlısıyla doğanın kalbidir.",
        "tip": "Ayder Yaylası'nda dumanı tüten tereyağlı mıhlamaya mısır ekmeğini banıp ardından taze çay için."
    },
    "Sakarya": {
        "dishes": ["🍢 Adapazarı Islama Köftesi", "🎃 Sakarya Kabak Tatlısı", "🍗 Çerkes Tavuğu", "🥖 Dartılı Keşkek"],
        "desc": "Kemik suyu ve kırmızı biberli sosa batırılarak ızgarada kızartılan ekmek dilimleri üzerinde sunulan efsane Islama köftesi ve kireçte bekletilerek pişirilen çıtır kabak tatlısıyla ünlüdür.",
        "tip": "Islama köftenin ardından üzerine bol tahin ve fındık serpilmiş çıtır Sakarya kabak tatlısı şarttır."
    },
    "Samsun": {
        "dishes": ["🍕 Bafra & Terme Pidesi", "🥐 Çarşamba Kıvratması", "🍗 Kaz Tiridi", "🍢 Nokul"],
        "desc": "Uzun, çıtır ve kapalı hamurunda bol kıymalı harçla fırınlanıp üzerine tereyağı sürülen Bafra pidesi ve cevizli çıtır fındıklı Çarşamba kıvratmasıyla Karadeniz'in en zengin mutfaklarındandır.",
        "tip": "Pazar sabahı Bafra'da fırın kuyruğuna girip sıcak tereyağlı kapalı Bafra pidesini deneyin."
    },
    "Şanlıurfa": {
        "dishes": ["🥩 Gerçek Urfa Çiğ Köftesi", "🍢 Urfa Kebabı", "🍕 Urfa Lahmacunu", "🍮 Şıllık Tatlısı", "☕ Mırra"],
        "desc": "Tarihin sıfır noktası Şanlıurfa; taş leğenlerde saatlerce yoğrulan tescilli çiğ köftesi, tırnak pide üstünde Urfa kebabı, cevizli şerbetli Şıllık tatlısı ve kulpsuz fincanda içilen acı Mırra kahvesiyle bir efsanedir.",
        "tip": "Geleneksel bir sıra gecesinde dumanı tüten lahmacun ve taze yoğrulmuş çiğ köftenin tadına varın."
    },
    "Siirt": {
        "dishes": ["🍖 Siirt Büryan Kebabı", "🍗 Perde Pilavı", "🥜 Siirt Fıstığı", "🥣 Rayoşu Meketir"],
        "desc": "Kuyu fırınlarında buharla pişirilen nar gibi büryan kebabı, keklik veya tavuk etiyle kekik kokulu hamur içinde pişirilen fes şeklindeki Perde pilavı ve iri Siirt fıstığıyla meşhurdur.",
        "tip": "Geleneksel bakır tepsilerde kekik kokan çıtır hamurlu Perde pilavını dilimleyerek servis ettirin."
    },
    "Sinop": {
        "dishes": ["🥟 Sinop Mantısı (Cevizli)", "🥐 Sinop Nokulu", "🌰 Kestane", "🐟 Taze Hamsi & Kalkan"],
        "desc": "Yarısı sarımsaklı yoğurtlu, diğer yarısı bol cevizli ve tereyağlı olarak iki lezzet tek tabakta sunulan tescilli Sinop mantısı ve üzümlü cevizli çıtır nokuluyla Karadeniz klasiğidir.",
        "tip": "Mantıyı mutlaka 'karışık' (yarısı cevizli, yarısı yoğurtlu) sipariş ederek iki zıt lezzetin uyumunu yaşayın."
    },
    "Şırnak": {
        "dishes": ["🍲 Suryaz Yemeği", "🥟 Kutlık (İçli Köfte)", "🥩 Hekeheşandi", "🥣 Meyre Çorbası"],
        "desc": "Cudi Dağı'nın eteklerinde yetişen şifalı suryaz otu kavurması, pirinç ve kıymayla yoğrulan haşlama köfte Hekeheşandi ve zengin dağ bitkileriyle hazırlanan yayla sofralarıyla tanınır.",
        "tip": "Geleneksel Şırnak ev yemekleri lokantasında yoğurtlu meyre çorbası ve sıcak kutlık tadın."
    },
    "Sivas": {
        "dishes": ["🍢 Sivas Köftesi", "🥐 Sivas Katmeri", "🌱 Madımak Aşı", "🥖 Sivas Pezik Turşusu"],
        "desc": "Yalnızca dana eti ve tuzla yoğrulup ekmeksiz baharatsız pişirilen tescilli Sivas köftesi, kat kat tel tel ayrılan sıcak katmeri ve kırların şifası madımak yemeğiyle ünlüdür.",
        "tip": "Sabah kahvaltısında fırından yeni çıkmış sıcak Sivas katmerini tulum peyniriyle tüketin."
    },
    "Tekirdağ": {
        "dishes": ["🍢 Tekirdağ Köftesi", "🍮 Hayrabolu Tatlısı", "🧀 Peynir Helvası", "🥖 Tekirdağ Rakı Mezesi"],
        "desc": "Özel baharat dengesi ve irmikle yoğrulup yanında acı kırmızı biber salçasıyla sunulan meşhur Tekirdağ köftesi ve üzerinde tahinle kaymak bulunan Hayrabolu tatlısıyla Trakya'nın gururudur.",
        "tip": "Marmara Denizi kıyısındaki köftecilerde acı soslu köftenin ardından fırınlanmış Hayrabolu tatlısı yiyin."
    },
    "Tokat": {
        "dishes": ["🥘 Tokat Kebabı", "🥬 Tokat Yaprağı Sarması", "🥖 Çökelekli Gözleme", "🍷 Tokat Kuşburnusu"],
        "desc": "Özel fırınlarda şişlere dizilen kuzu eti, patlıcan, domates, sarımsak ve patatesin odun ateşinde pişip lavaşla sunulduğu Tokat kebabı ve dünyaca ünlü incecik asma yapraklarıyla bilinir.",
        "tip": "Tokat kebabı sipariş ettiğinizde etin yağıyla ıslatılmış fırın lavaşlarını sıcağı sıcağına tüketin."
    },
    "Trabzon": {
        "dishes": ["🍢 Akçaabat Köftesi", "🫕 Trabzon Kuymağı", "🐟 Hamsili Pilav", "🍞 Vakfıkebir Ekmeği", "🥮 Trabzon Burması"],
        "desc": "Sarımsak ve dana kıymasının meşe kömüründe harikalar yarattığı Akçaabat köftesi, tereyağıyla uzayan meşhur kuymağı, taş fırınlarda pişen koca Vakfıkebir ekmeğiyle Karadeniz'in gözbebeğidir.",
        "tip": "Akçaabat sahilinde köftenin yanında taze yayık ayranı için, kahvaltıda ise kuymak banın."
    },
    "Tunceli": {
        "dishes": ["🫓 Babuko (Zerefet)", "🥣 Şir", "🥘 Gömme", "🌱 Dağ Sarımsağı & Işkın"],
        "desc": "Munzur Vadisi'nin tertemiz doğasında hamur çanağının içine dökülen sarımsaklı ayran ve kızgın tereyağıyla sunulan kadim yemek Babuko ve dağ kekiğiyle yoğrulan yemekleriyle otantiktir.",
        "tip": "Munzur Çayı kıyısında doğa manzarasına karşı sarımsaklı ve tereyağlı sıcak Babuko tadın."
    },
    "Uşak": {
        "dishes": ["🥣 Uşak Tarhanası", "🥘 Alaca Çorba", "🥟 Ebem Köftesi", "🍮 Demir Tatlısı"],
        "desc": "Ev yoğurdu, domates, nane ve taze biberle 21 gün fermente edilerek güneşte kurutulan coğrafi işaretli şifa deposu Uşak tarhanası ve demir kalıplarla kızartılan tatlısıyla meşhurdur.",
        "tip": "Kış günlerinde sabah erkenden bol tereyağlı ve hafif pul biberli sıcak Uşak tarhanası için."
    },
    "Van": {
        "dishes": ["🍳 Meşhur Van Kahvaltısı", "🧀 Van Otlu Peyniri", "🐟 Van Balığı (İnci Kefali)", "🍲 Keledoş"],
        "desc": "Otuzdan fazla çeşidiyle Guinness rekorlu meşhur Van kahvaltısı, dağ kekiği ve sirmo otuyla hazırlanan otlu peyniri ve sodalı gölde yaşayan tandırda İnci kefaliyle bir şölendir.",
        "tip": "Van Kalesi eteğindeki kahvaltı salonlarında sıcak murtuğa, kavut ve taze otlu peynir deneyin."
    },
    "Yalova": {
        "dishes": ["🍮 Termal Tatlısı", "🍢 Yalova Köftesi", "🥣 Milföylü Yalova Çorbası", "🥝 Yalova Kivisi"],
        "desc": "Kaplıcalarıyla ünlü Termal ilçesinin fıstıklı ve elmalı meşhur tatlısı, taze kivisi ve taze deniz havasında pişirilen köftesiyle Marmara'nın yeşil ve huzurlu lezzet durağıdır.",
        "tip": "Termal kaplıca keyfinin ardından üzerine pudra şekeri serpilmiş sıcak fıstıklı Termal tatlısı yiyin."
    },
    "Yozgat": {
        "dishes": ["🥘 Yozgat Testi Kebabı", "🥣 Arabaşı Çorbası & Hamuru", "🥖 Parmak Çörek", "🌱 Madımak"],
        "desc": "Kuzu eti ve sarımsakla toprak testide közlenip kırılan Testi kebabı, soğuk kış gecelerinde çiğnenmeden yutulan kaygan hamuruyla içilen acılı sıcak Arabaşı çorbasıyla ünlüdür.",
        "tip": "Çamlık Milli Parkı eteğindeki lokantalarda taş fırından yeni çıkmış sıcak parmak çörek yiyin."
    },
    "Zonguldak": {
        "dishes": ["🥧 Zonguldak Kömeci", "🥣 Uğmaç Çorbası", "🍮 Beyaz Baklava", "🥛 Çaycuma Manda Yoğurdu"],
        "desc": "Cevizli ve pırasalı kat kat açılan taş fırın kömeci, sütlü unlu Uğmaç çorbası, cevizli bembeyaz kabaran bayram baklavası ve Çaycuma'nın katıksız manda yoğurduyla zengindir.",
        "tip": "Karadeniz kıyısında taze fırın kömeci eşliğinde koyu kıvamlı manda yoğurdu tadın."
    }
}

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cuisines.json")

def main():
    print(f"Toplam il sayısı: {len(CUISINES)}")
    assert len(CUISINES) == 81, f"81 il olmalı, mevcut: {len(CUISINES)}"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(CUISINES, f, ensure_ascii=False, indent=2)
    print(f"Başarıyla kaydedildi: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
