// 画面の撮影（試作の確認用）: node shot.js <site/xxx.html> <#hash> <出力.png> [幅] [クリックするセレクタ]
const {chromium}=require('playwright');const [,,f,h,o,w,c]=process.argv;
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:+(w||1000),height:900}});
await p.goto('file://'+require('path').resolve(f)+h);await p.waitForTimeout(300);if(c){await p.click(c);await p.waitForTimeout(300);}
await p.screenshot({path:o,fullPage:!c});await b.close();})();
