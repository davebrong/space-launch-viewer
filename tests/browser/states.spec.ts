import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
test.use({baseURL:'http://127.0.0.1:3091'});
test.afterEach(async({page})=>{
  // Keep the next viewport isolated even when an assertion fails before normal cleanup.
  const csrf=await page.evaluate(()=>document.cookie.split('; ').find(x=>x.startsWith('lv_csrf='))?.split('=')[1]);
  if(csrf)await page.request.delete('/api/v1/__test__/launches',{headers:{Origin:'http://127.0.0.1:3091','X-CSRF-Token':csrf}});
});

test('synthetic edge cases through actual API, database and UI',async({page},info)=>{
  test.setTimeout(180000);
  page.setDefaultTimeout(15000);
  await page.goto('/');
  await page.getByLabel('US ZIP code').fill('21201');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(page.getByRole('heading',{name:'Launches & your sky'})).toBeVisible();
  const locationId=await page.evaluate(()=>localStorage.getItem('lv_location'));
  const csrf=()=>page.evaluate(()=>document.cookie.split('; ').find(x=>x.startsWith('lv_csrf='))!.split('=')[1]);
  const reports:{mode:string;advice:string;band:boolean}[]=[];
  for(const mode of ['reconstructed','official','hazard','stale','window','date','unknown','scrubbed','completed','hold']){
    const response=await page.request.post('/api/v1/__test__/seed',{headers:{Origin:'http://127.0.0.1:3091','X-CSRF-Token':await csrf()},data:{location_id:locationId,mode}});
    expect(response.ok()).toBeTruthy();
    const {id}=await response.json();
    await page.goto('/launches/'+id);
    const advice=page.locator('.advice-panel h2');
    await expect(advice).toHaveText(mode==='completed'?'Approximate viewing window':mode==='official'?'Worth a look':mode==='reconstructed'||mode==='window'?'Possible':'Not enough data');
    const band=page.locator('svg[role="img"]');
    if(['hazard','stale','official'].includes(mode))await expect(band).toHaveCount(0);
    if(mode==='reconstructed'){
      await expect(band).toHaveCount(1);
      await page.screenshot({path:`evidence/build/${info.project.name}-synthetic-band.png`,fullPage:true});
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
      fs.writeFileSync(`evidence/build/${info.project.name}-band-axe.json`,JSON.stringify(result.violations,null,2));
      expect(result.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
    }
    if(mode==='official')await expect(page.getByText('Official viewing interval:',{exact:false})).toBeVisible();
    if(mode==='window')await expect(page.getByText('Conditional launch-time alternatives',{exact:false})).toBeVisible();
    if(mode==='date')await expect(page.locator('.page-heading')).toContainText('date only');
    if(mode==='unknown')await expect(page.getByRole('button',{name:'Download calendar .ics'})).toBeDisabled();
    if(mode==='completed'){
      await expect(page.getByText('Review this launch',{exact:true})).toBeVisible();
      await expect(band).toHaveCount(1);
      await expect(page.getByText('nonactionable completed',{exact:true})).toHaveCount(0);
      await expect(page.getByText('Essential data incomplete or stale',{exact:true})).toHaveCount(0);
      await expect(page.getByText('This forecast was issued after the launch',{exact:false})).toBeVisible();
      await expect(page.getByRole('button',{name:'Download launch record .ics'})).toBeEnabled();
    }
    reports.push({mode,advice:await advice.innerText(),band:await band.count()>0});
  }
  await page.getByRole('link',{name:'Reminders',exact:true}).click();
  await page.getByRole('button',{name:'Preview local reminder times'}).click();
  await expect(page.getByRole('heading',{name:'Preview at your viewing location'})).toBeVisible();
  await page.getByRole('button',{name:'Save preferences for all supported launches'}).click();
  await page.getByRole('button',{name:'Edit preferences'}).click();
  await page.getByLabel('Include Possible opportunities',{exact:false}).check();
  await page.getByRole('button',{name:'Save subscription changes'}).click();
  await expect(page.locator('.subscription-row')).toContainText('Possible and Worth a look');
  await page.goto('/observations/new');
  await page.getByLabel('Viewing time (UTC)',{exact:true}).fill(new Date().toISOString().slice(0,19).replace(/:00$/, ''));
  await page.getByLabel('Record as a retrospective report',{exact:false}).check();
  await page.getByRole('combobox',{name:/^Outcome/}).selectOption('inconclusive');
  await page.getByLabel('Actual cloud conditions').fill('Synthetic browser test clouds');
  await page.getByLabel('Viewing notes').fill('Synthetic test only; no real sighting');
  await page.getByLabel('I consent to archiving',{exact:false}).check();
  await page.getByRole('button',{name:'Record attempt'}).click();
  await expect(page.getByText('Viewing attempt recorded',{exact:false})).toBeVisible();
  await page.getByRole('link',{name:'Operator',exact:false}).click();
  await page.getByLabel('Operator secret').fill('wrong-secret');
  await page.getByRole('button',{name:'Inspect ingestion'}).click();
  await expect(page.getByRole('alert').filter({hasText:'Operator authentication required'})).toBeVisible();
  await page.getByLabel('Operator secret').fill('synthetic-browser-operator-secret');
  await page.getByRole('button',{name:'Inspect ingestion'}).click();
  await expect(page.getByRole('heading',{name:'Coverage & queue'})).toBeVisible();
  await page.getByLabel('Audit reason').fill('Synthetic browser test disable');
  await page.getByRole('button',{name:'Disable',exact:true}).first().click();
  await expect(page.getByText('Mission change saved and audited',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Enable',exact:true})).toHaveCount(1);
  await page.getByLabel('Registry package JSON').fill('{}');
  await page.getByRole('button',{name:'Validate and import version'}).click();
  await expect(page.getByRole('alert').filter({hasText:'Registry rejected'})).toBeVisible();
  await page.request.delete('/api/v1/__test__/launches',{headers:{Origin:'http://127.0.0.1:3091','X-CSRF-Token':await csrf()}});
  await page.goto('/launches');
  await expect(page.getByRole('heading',{name:'No launches to show'})).toBeVisible();
  fs.writeFileSync(`evidence/build/${info.project.name}-ui-states.json`,JSON.stringify(reports,null,2));
});
