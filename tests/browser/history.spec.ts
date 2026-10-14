import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('past launches browse real provider records independently of viewing estimates',async({page},info)=>{
  test.setTimeout(120000);
  await page.goto('/');
  await page.getByLabel('US ZIP code').fill('fl-zip');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  const filter=page.getByRole('combobox',{name:'Show'});
  await filter.selectOption('past');
  await expect(page.getByRole('heading',{name:'Past launches',exact:true})).toBeVisible();
  const records=page.locator('article.launch-card');
  await expect(records).toHaveCount(100,{timeout:70000});
  await expect(records.first()).toContainText('Dragon CRS-2 SpX-35');
  await expect(records.first()).toContainText('Oct 13, 2026');
  await expect(records.first()).toContainText('6:33 AM EDT');
  await expect(records.first()).toContainText('Record updated');
  await expect(records.first().getByRole('link',{name:'View API record'})).toHaveAttribute('href',/ll.thespacedevs.com\/2.3.0\/launches\//);
  await expect(page.getByText('Showing 100 of 1,414 historical records.',{exact:false})).toBeVisible();
  // This launch is outside today's upcoming catalog; its detail must work on its own.
  const historic=records.filter({hasText:'NROL-97'}).first();
  await historic.getByRole('link',{name:'Could I have seen it?'}).click();
  await expect(page.getByRole('heading',{name:'NROL-97',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Potentially visible from ZIP fl-zip'})).toBeVisible();
  await expect(page.getByRole('heading',{name:/Look south/})).toBeVisible();
  await expect(page.getByText('No matching prelaunch cloud forecast is available.',{exact:false})).toBeVisible();
  await expect(page.getByText('Oct 1, 2026',{exact:false}).first()).toBeVisible();
  // Direct entry must return to the archive even if the saved filter was Viewable.
  await page.evaluate(()=>localStorage.setItem('lv_filter_v2','viewable'));
  await page.reload();
  await expect(page.getByRole('heading',{name:'Potentially visible from ZIP fl-zip'})).toBeVisible();
  const detailAxe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  expect(detailAxe.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
  await page.screenshot({path:`evidence/build/history-detail-${info.project.name}.png`,fullPage:false});
  await page.getByRole('link',{name:'Past launches',exact:false}).click();
  await expect(records).toHaveCount(100);
  await page.screenshot({path:`evidence/build/history-${info.project.name}.png`,fullPage:false});
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  expect(axe.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
  const width=await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
  await page.getByRole('button',{name:'Load older launches'}).click();
  await expect(records).toHaveCount(200,{timeout:70000});
  const ids=await records.getByRole('link',{name:'View API record'}).evaluateAll(links=>links.map(link=>link.getAttribute('href')));
  expect(new Set(ids).size).toBe(200);
  await page.reload();
  await expect(filter).toHaveValue('past');
  await expect(records).toHaveCount(100,{timeout:70000});
  await filter.selectOption('viewable');
  await expect(page.getByRole('heading',{name:'Past launches',exact:true})).toHaveCount(0);
  // Bandwagon-5 and Amazon Leo LV-01 (published headings) on 2026-10-14; CRS-35 has left the 30-day horizon.
  await expect(page.locator('a.launch-card')).toHaveCount(2);
  await page.goto('/privacy');
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'Delete my data'}).click();
  await expect(page.getByText('Your data has been deleted',{exact:false})).toBeVisible();
});
