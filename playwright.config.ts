import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests/browser',timeout:60000,workers:1,fullyParallel:false,
  expect:{timeout:15000},
  webServer:{command:(process.platform==='win32'?'.venv\\Scripts\\python.exe':'.venv/bin/python')+' -m tests.browser_server',url:'http://127.0.0.1:3091/api/v1/health/live',reuseExistingServer:false,timeout:60000},
  reporter:[['list'],['json',{outputFile:'evidence/build/playwright.json'}]],
  use:{baseURL:process.env.LV_BROWSER_URL||'http://127.0.0.1:3007',browserName:'chromium',timezoneId:'America/Los_Angeles',trace:'retain-on-failure',screenshot:'only-on-failure'},
  projects:[{name:'desktop',use:{viewport:{width:1440,height:1000}}},{name:'mobile',use:{viewport:{width:360,height:800}}}]
});
