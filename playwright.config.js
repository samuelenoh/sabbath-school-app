const {defineConfig}=require('@playwright/test');
const path=require('node:path');
process.env.SSMS_DEMO_PASSWORD ||= require('node:crypto').randomBytes(24).toString('base64url');
module.exports=defineConfig({
 testDir:'./e2e',fullyParallel:false,workers:1,
 use:{baseURL:'http://127.0.0.1:8011',trace:'retain-on-failure'},
 webServer:{command:`"${process.env.PYTHON_BIN||'python'}" server.py --demo --port 8011`,url:'http://127.0.0.1:8011',reuseExistingServer:false,
 env:{SSMS_DB:path.resolve('.e2e-data',`test-${Date.now()}.sqlite3`),WHATSAPP_MODE:'dry_run',SSMS_ENV:'development',SSMS_DEMO_PASSWORD:process.env.SSMS_DEMO_PASSWORD},timeout:30000}
});
