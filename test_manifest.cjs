const fs = require('fs');
const content = fs.readFileSync('src-tauri/assets/resources/manifest.json', 'utf8');
const val = JSON.parse(content);
const pack_ver = "1.10.1";
const patch_ver = "1.2";
const formatted_name = `§eActions & Stuff §dRTX §b${pack_ver.replace('v', '')} §5V${patch_ver}`;
val.header.name = formatted_name;
console.log(val.header.name);
