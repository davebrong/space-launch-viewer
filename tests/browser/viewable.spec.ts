import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Live expectations recorded in evidence/build/flight-plan-audit/live-validation-2026-10-14.json.
// Distant estimates come only from a mission-specific published departure heading (Next Spaceflight)
// and NAVCEN hazard areas; missions without route information are labeled, never guessed.
test('viewable defaults to published-heading ZIP plans; all labels missing route coverage and hides secondary features',async({page},info)=>{
  await page.goto('/');
  await page.getByLabel('US ZIP code').fill('19102');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  const filter=page.getByRole('combobox',{name:'Show'});
  await expect(filter).toHaveValue('viewable');
  const dragon=page.locator('a.launch-card[href="/launches/bf2c3027-a314-403e-a416-2bfd5d165ad1"]');
  const bandwagon=page.locator('a.launch-card[href="/launches/3b430f81-0ff1-4d85-8a1a-cef0de326198"]');
  const vulcan=page.locator('a.launch-card[href="/launches/ef9850ad-1096-425b-9d27-f7bbd186e61a"]');
  const starliner=page.locator('a.launch-card[href="/launches/07e945c1-2ec6-4d29-a500-1afbe920440f"]');
  // Vulcan has a published heading but only a date: the list shows a liftoff-relative window.
  await expect(vulcan).toContainText('Clear-sky estimate · time TBA');
  await expect(vulcan.locator('.viewing-direction')).toHaveText('Look south → southeast → east in clear skies · 1–11 minutes after liftoff');
  // CRS-35 launched yesterday (outside today..+30 days); Bandwagon-5 only grazes the Philadelphia horizon.
  await expect(dragon).toHaveCount(0);
  await expect(bandwagon).toHaveCount(0);
  await expect(page.getByRole('link',{name:'Privacy',exact:true})).toHaveCount(0);
  await expect(page.getByRole('link',{name:'Observations',exact:true})).toHaveCount(0);
  const coverage=page.locator('details.coverage');
  await expect(coverage.locator('summary')).toHaveText(/^Route coverage: \d+ of \d+ launches due within 7 days or already flown have published route information$/);
  await coverage.locator('summary').click();
  await expect(coverage).toContainText('later or undated missions are not expected to have routes yet');
  await expect(coverage).toContainText('departure heading:');
  await expect(coverage).toContainText('missing coverage is not a negative visibility result');
  await page.screenshot({path:`evidence/build/viewable-${info.project.name}.png`,fullPage:true});
  await page.screenshot({path:`evidence/build/viewable-${info.project.name}-viewport.png`,fullPage:false});
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  expect(axe.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
  await filter.selectOption('all');
  await expect(dragon).toContainText('Clear-sky estimate');
  await expect(dragon).toHaveClass(/unavailable/);
  await expect(bandwagon).toContainText('Grazes your horizon (modeled)');
  await expect(bandwagon).toHaveClass(/unavailable/);
  await expect(bandwagon.locator('.viewing-direction')).toHaveCount(0);
  // Undated missions are not expected to have routes yet; in-window ones may be genuinely missing.
  const noRouteLabel=/No published route found|Route not published yet/;
  const noRoute=page.locator('a.launch-card').filter({hasText:noRouteLabel}).first();
  await expect(noRoute).toHaveClass(/unavailable/);
  await expect(noRoute.locator('.viewing-direction')).toHaveCount(0);
  await page.reload();
  await expect(filter).toHaveValue('all');
  // A mission without any route information: no estimate, no guessed direction.
  await noRoute.click();
  const missing=page.locator('.notice-strip').filter({hasText:'No viewing estimate'});
  await expect(missing).toContainText(noRouteLabel);
  await expect(missing).toContainText('does not guess its direction');
  await expect(page.locator('.route-panel h2')).toHaveText(noRouteLabel);
  await expect(page.locator('.route-panel .source h3')).toHaveCount(0);
  await page.locator('.route-panel').getByText('Sources checked',{exact:true}).click();
  await expect(page.locator('.route-panel')).toContainText('Next Spaceflight · ');
  await expect(page.locator('.route-panel')).toContainText('US Coast Guard NAVCEN SOLAR · ');
  await expect(page.getByRole('link',{name:'Record a viewing attempt',exact:false})).toHaveCount(0);
  await page.getByRole('link',{name:'All launches',exact:false}).click();
  // Bandwagon-5 from Philadelphia: published southeast departure, modeled ascent only grazes the horizon.
  await bandwagon.click();
  await expect(page.locator('.advice-panel h2')).toHaveText('Only grazes your horizon');
  await expect(page.locator('.route-basis')).toContainText('The rocket departs southeast, as published by Next Spaceflight');
  // No observer direction is offered when the modeled ascent never clears the horizon.
  await expect(page.locator('.route-basis')).not.toContainText('you would look');
  await expect(page.locator('.route-basis')).not.toContainText('you would also look');
  await expect(page.getByText('Clear-sky estimate',{exact:true})).toBeVisible();
  await expect(page.getByText('0 of 15 modeled paths visible',{exact:true})).toBeVisible();
  await expect(page.locator('.route-panel h3').first()).toHaveText('Published departure heading: southeast from the pad');
  await page.getByRole('link',{name:'All launches',exact:false}).click();
  await filter.selectOption('viewable');
  await expect(filter.locator('option')).toHaveText(['Viewable','All','Past launches']);
  await page.getByRole('button',{name:'Change',exact:true}).click();
  await page.getByLabel('US ZIP code').fill('32801');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  // Near the Cape the published heading (not proximity) drives Bandwagon-5's estimate.
  await expect(bandwagon).toContainText('Clear-sky estimate');
  await expect(bandwagon).not.toContainText('Nearby launch estimate');
  await expect(bandwagon.locator('.viewing-direction')).toHaveText('Look east → southeast in clear skies');
  await expect(vulcan.locator('.viewing-direction')).toHaveText('Look east → northeast in clear skies · 0–11 minutes after liftoff');
  await page.screenshot({path:`evidence/build/viewable-near-cape-${info.project.name}.png`,fullPage:true});
  const nearbyAxe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  expect(nearbyAxe.violations.filter(v=>['critical','serious'].includes(v.impact||''))).toEqual([]);
  await bandwagon.click();
  await expect(page.locator('.advice-panel h2')).toHaveText('Look east → southeast in clear skies');
  await expect(page.locator('.plan-time')).toContainText('6:30');
  await expect(page.locator('.plan-time')).toContainText('6:41');
  await expect(page.locator('.plan-time')).toContainText('EDT');
  await expect(page.locator('.route-basis')).toContainText('FROM THE PAD');
  await expect(page.locator('.route-basis')).toContainText('The rocket departs southeast');
  // Observer direction and pad departure are reported separately.
  await expect(page.locator('.route-basis')).toContainText(/From your location you would (also )?look east → southeast/);
  await expect(page.getByText('15 of 15 modeled paths visible',{exact:true})).toBeVisible();
  await expect(page.locator('.route-panel h2')).toHaveText('Route information found');
  await expect(page.locator('.route-panel h3')).toHaveText(['Published departure heading: southeast from the pad']);
  await expect(page.locator('.route-panel').getByRole('link',{name:'Next Spaceflight ↗'})).toHaveAttribute('href','https://nextspaceflight.com/launches/details/8362/');
  await page.locator('.route-panel').getByText('Sources checked',{exact:true}).click();
  await expect(page.locator('.route-panel')).toContainText('US Coast Guard NAVCEN SOLAR · No published route found');
  await page.screenshot({path:`evidence/build/viewable-near-cape-detail-${info.project.name}.png`,fullPage:true});
  await page.getByRole('link',{name:'All launches',exact:false}).click();
  await vulcan.click();
  await expect(page.locator('.advice-panel h2')).toHaveText('Look east → northeast in clear skies');
  await expect(page.locator('.plan-time')).toHaveText('About 0–11 minutes after liftoff · launch time to be announced');
  await page.getByRole('link',{name:'All launches',exact:false}).click();
  // Nearby (<100 km) missions without a published heading keep the nearby estimate.
  await filter.selectOption('all');
  await expect(starliner).toContainText('Nearby launch estimate');
  await starliner.click();
  await expect(page.getByText('Launch time to be announced',{exact:true})).toBeVisible();
  await expect(page.getByText(/about \d+ km away/)).toBeVisible();
  await expect(page.locator('.route-panel h2')).toHaveText('Route not published yet');
  await expect(page.locator('.route-panel')).toContainText('usually publish a few days before launch');
  await page.getByRole('link',{name:'All launches',exact:false}).click();
  await filter.selectOption('viewable');
  await page.getByRole('button',{name:'Change',exact:true}).click();
  await page.getByLabel('US ZIP code').fill('19102');
  await page.getByRole('button',{name:'Find location'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(vulcan.locator('.viewing-direction')).toHaveText('Look south → southeast → east in clear skies · 1–11 minutes after liftoff');
  await expect(bandwagon).toHaveCount(0);
  await expect(dragon).toHaveCount(0);
  await page.getByRole('button',{name:'Change',exact:true}).click();
  await page.getByRole('button',{name:'Enter coordinates'}).click();
  await page.getByLabel('Latitude',{exact:true}).fill('-35');
  await page.getByLabel('Longitude',{exact:true}).fill('140');
  await page.getByRole('button',{name:'Review point'}).click();
  await page.getByRole('button',{name:'Confirm this location'}).click();
  await expect(page.getByRole('heading',{name:'No viewing plans for this location'})).toBeVisible();
  await expect(vulcan).toHaveCount(0);
  // Only this disposable test session is removed, via the retained direct page.
  await page.goto('/privacy');
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'Delete my data'}).click();
  await expect(page.getByText('Your data has been deleted',{exact:false})).toBeVisible();
});
