import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';

test('A distant ZIP can review the completed CRS-35 launch-day plan from its published heading',async({page},info)=>{
  await page.goto('/');
  await page.getByLabel('US ZIP code').fill('19102');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  const path='/launches/bf2c3027-a314-403e-a416-2bfd5d165ad1';
  const card=page.locator(`a.launch-card[href="${path}"]`);
  // Launched 2026-10-13: outside the Viewable horizon (today..+30 days) but still listed under All.
  await expect(page.getByRole('combobox',{name:'Show'})).toHaveValue('viewable');
  await expect(card).toHaveCount(0);
  await page.getByRole('combobox',{name:'Show'}).selectOption('all');
  await expect(card).toContainText('completed');
  await expect(card).toContainText('Clear-sky estimate');
  // Badges keep the label's sentence case.
  await expect(card.locator('.badge')).toHaveCSS('text-transform','none');
  await card.click();
  await expect(page.getByText('Launch-day plan',{exact:true})).toBeVisible();
  // The completed-launch wording does not switch after loading: no review fallback beside a launch-day plan.
  await expect(page.locator('.advice-panel .eyebrow')).toHaveText('LAUNCH-DAY VIEWING PLAN');
  await expect(page.getByText('Review this launch',{exact:true})).toHaveCount(0);
  const observer=page.locator('.advice-panel h2');
  // Headings are swept over the published northeast quadrant narrowed to the NAVCEN hazard bearings (15°–60°).
  await expect(observer).toHaveText('Look south → southeast → east → northeast in clear skies');
  await expect(page.locator('.plan-time')).toContainText('6:33');
  await expect(page.locator('.plan-time')).toContainText('6:45');
  await expect(page.locator('.plan-time')).toContainText('EDT');
  await expect(page.getByText('Clear-sky estimate',{exact:true})).toBeVisible();
  await expect(page.getByText('15 of 15 modeled paths visible',{exact:true})).toBeVisible();
  // Pad departure direction is published separately from where this observer looks.
  const departure=page.locator('.route-basis');
  await expect(departure).toContainText('FROM THE PAD');
  await expect(departure.locator('strong')).toHaveText('northeast');
  await expect(departure).toContainText('The rocket departs northeast, as published by Next Spaceflight');
  await expect(departure).toContainText('From your location you would look south → southeast → east → northeast, calculated from your position.');
  await expect(departure).not.toContainText('would also look');
  const route=page.locator('.route-panel');
  await expect(route.locator('.eyebrow')).toHaveText('MISSION ROUTE INFORMATION');
  await expect(route.locator('h2')).toHaveText('Route information found');
  await expect(route.locator('.source h3')).toHaveText(['Published departure heading: northeast from the pad','Hazard area (not a flight path)']);
  await expect(route).toContainText('Your viewing direction is calculated separately from your location.');
  await expect(route).toContainText('Published hazard areas lie toward compass bearings 15°–60° (NNE–ENE) from the pad, 35–552 km away (notice CGD-SE BNM 9079-26). Altitude and timed visibility are unresolved.');
  await expect(route).toContainText('not the flight path');
  await expect(route.getByRole('link',{name:'Next Spaceflight ↗'})).toHaveAttribute('href','https://nextspaceflight.com/launches/details/6917/');
  await expect(route.getByRole('link',{name:'US Coast Guard NAVCEN SOLAR ↗'})).toHaveAttribute('href','https://www.navcen.uscg.gov/chart');
  await expect(route.getByText('Not a timed trajectory: no published altitude or position over time.',{exact:true})).toHaveCount(2);
  await expect(route.getByText('Source data & hash',{exact:true})).toHaveCount(2);
  await expect(page.getByText('Viewing estimate unavailable',{exact:true})).toHaveCount(0);
  await expect(page.getByText('nonactionable completed',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Essential data incomplete or stale',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Plan a look outside'})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'No supported sky path'})).toHaveCount(0);
  await expect(page.getByText('See model & assumptions')).toBeVisible();
  await expect(page.getByRole('img',{name:'Approximate direction sectors; exact values are in the table below'})).not.toBeVisible();
  await expect(page.getByRole('button',{name:'Download launch record .ics'})).toBeEnabled();
  await expect(page.getByText('No prelaunch cloud forecast was saved for this viewing window.',{exact:true})).toBeVisible();
  await expect(page.getByText('minutes before local sunrise.',{exact:false})).toBeVisible();
  const size=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
  expect(size.scroll).toBeLessThanOrEqual(size.width);
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  expect(axe.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
  fs.writeFileSync(`evidence/build/planning-${info.project.name}-axe.json`,JSON.stringify(axe.violations,null,2));
  await page.screenshot({path:`evidence/build/planning-${info.project.name}.png`,fullPage:true});
  await page.screenshot({path:`evidence/build/planning-${info.project.name}-viewport.png`,fullPage:false});
  await page.getByText('See model & assumptions').click();
  await expect(page.getByRole('img',{name:'Approximate direction sectors; exact values are in the table below'})).toBeVisible();
  // Remove only this test's disposable browser session, not the user's session.
  await page.goto('/privacy');
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'Delete my data'}).click();
  await expect(page.getByText('Your data has been deleted',{exact:false})).toBeVisible();
});

test('unknown provider placeholders never create exact date groups',async({page})=>{
  await page.goto('http://127.0.0.1:3091/');
  await page.getByLabel('US ZIP code').fill('19102');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(page.getByRole('heading',{name:'Launches & your sky'})).toBeVisible();
  const locationId=await page.evaluate(()=>localStorage.getItem('lv_location'));
  const csrf=await page.evaluate(()=>document.cookie.split('; ').find(s=>s.startsWith('lv_csrf='))!.split('=')[1]);
  const response=await page.request.post('http://127.0.0.1:3091/api/v1/__test__/seed',{headers:{Origin:'http://127.0.0.1:3091','X-CSRF-Token':csrf},data:{location_id:locationId,mode:'unknown'}});
  expect(response.ok()).toBeTruthy();
  const {id}=await response.json();
  await page.reload();
  await page.getByRole('combobox',{name:'Show'}).selectOption('all');
  const group=page.locator('.launch-group').filter({has:page.locator(`a[href="/launches/${id}"]`)});
  await expect(group.locator('h2.date-heading')).toHaveText('Date to be announced');
  await expect(group.locator(`a[href="/launches/${id}"]`)).toContainText('Launch time not yet confirmed');
  await page.route('**/api/v1/assessments',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({message:'Synthetic assessment outage'})}));
  await page.goto('http://127.0.0.1:3091/launches/'+id);
  await expect(page.getByRole('heading',{name:'Viewing details unavailable',exact:true})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'Synthetic assessment outage'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Loading viewing details…'})).toHaveCount(0);
  await page.unroute('**/api/v1/assessments');
  await page.goto('http://127.0.0.1:3091/launches/nonexistent-qa-mission');
  await expect(page.getByRole('heading',{name:'Launch unavailable',exact:true})).toBeVisible();
});
