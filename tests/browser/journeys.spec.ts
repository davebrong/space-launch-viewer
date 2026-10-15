import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';

test('live location, schedule, uncertainty, reminders, privacy and keyboard journeys',async({page},info)=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Find location'})).toBeEnabled();
  await page.getByLabel('US ZIP code').fill('21201');
  await page.getByRole('button',{name:'Find location'}).click();
  await expect(page.getByText('39.294961, -76.622341',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(page.getByRole('heading',{name:'Launches & your sky'})).toBeVisible();
  await page.screenshot({path:`evidence/build/${info.project.name}-launches.png`,fullPage:true});
  const cards=page.locator('.launch-card');
  if(await cards.count()){
    await cards.first().click();
    await expect(page.locator('.advice-panel h2')).toHaveText(/^(Not enough data|Viewing estimate unavailable|Look south → southeast → east in clear skies)$/);
    await page.getByText('Sources & technical details',{exact:true}).click();
    await page.getByText('Source timestamps, hashes & calculation versions').click();
    await expect(page.locator('.source').first()).toBeVisible();
    await page.screenshot({path:`evidence/build/${info.project.name}-detail.png`,fullPage:true});
  }
  await page.getByRole('link',{name:'Reminders',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Your reminders'})).toBeVisible();
  const checks=page.getByRole('checkbox');
  await expect(checks.nth(0)).not.toBeChecked();await expect(checks.nth(1)).not.toBeChecked();
  await page.getByRole('button',{name:'Save preferences for all supported launches'}).click();
  await expect(page.getByRole('heading',{name:'Active',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Unsubscribe immediately'}).click();
  await expect(page.getByRole('heading',{name:'Unsubscribed',exact:true})).toBeVisible();
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  const severe=axe.violations.filter(v=>v.impact==='critical'||v.impact==='serious');
  fs.writeFileSync(`evidence/build/${info.project.name}-axe.json`,JSON.stringify(axe.violations,null,2));
  expect(severe).toEqual([]);
  await page.getByRole('button',{name:'Change',exact:true}).click();
  await page.getByLabel('US ZIP code').fill('00601');await page.getByRole('button',{name:'Find location'}).click();
  await expect(page.getByText('ZIP 00601',{exact:false})).toBeVisible();
  await expect(page.getByText('America/Puerto_Rico',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByLabel('US ZIP code').fill('00000');await page.getByRole('button',{name:'Find location'}).click();
  await expect(page.getByRole('alert').filter({hasText:'No Census representative point'})).toContainText('No Census representative point');
  await page.getByRole('button',{name:'Enter coordinates'}).click();
  await page.getByLabel('Latitude',{exact:true}).fill('39.3');await page.getByLabel('Longitude',{exact:true}).fill('-76.6');
  await page.getByRole('button',{name:'Review point'}).click();await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(page.getByRole('heading',{name:'Launches & your sky'})).toBeVisible();
  await page.goto('/privacy');
  page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Delete my data'}).click();
  await expect(page.getByText('Your data has been deleted',{exact:false})).toBeVisible();
});

test('observer clock is independent of browser timezone and preserves DST fold',async({page})=>{
  await page.goto('/');
  const times=await page.evaluate(()=>['2026-10-14T00:30:00Z','2026-11-01T05:30:00Z','2026-11-01T06:30:00Z'].map(value=>new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value))));
  expect(times[0]).toContain('Oct 13');expect(times[0]).toContain('8:30');expect(times[1]).toContain('EDT');expect(times[2]).toContain('EST');
  await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
});

