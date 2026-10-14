const {test,expect}=require('@playwright/test');
async function login(page,email='admin@ssms.local'){
 await page.route('**/api/lessons/current',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({available:true,day:'2026-10-14',quarter_title:'Synthetic quarterly',week_title:'Synthetic published week',week_number:3,week_start:'2026-10-10',week_end:'2026-10-16',daily_url:'https://absg.sspmadventist.org/en/2026-04/03/05',weekly_url:'https://absg.sspmadventist.org/en/2026-04/03'})}));
 await page.goto('/');await expect(page.getByRole('img',{name:'Seventh-day Adventist Church',exact:true})).toBeVisible();await expect.poll(()=>page.getByRole('img',{name:'Seventh-day Adventist Church',exact:true}).evaluate(img=>img.complete&&img.naturalWidth>0)).toBeTruthy();await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(process.env.SSMS_DEMO_PASSWORD);
 await page.getByRole('button',{name:'Sign in →',exact:true}).click();await expect(page.getByRole('heading',{name:'Welcome to your Sabbath School'})).toBeVisible();
}
test('all requested module screens render',async({page})=>{
 await login(page);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const [nav,heading] of [['Members','Members'],['Classes','Classes'],['Attendance','Sabbath attendance'],['Lesson study','Lesson study'],['Offerings','Offerings'],['Reports','Reports'],['Events','Events'],['Outreach','Outreach'],['WhatsApp','WhatsApp notifications'],['People & roles','People & roles'],['My account','My account']]){
  await page.getByRole('button',{name:nav,exact:true}).click();await expect(page.getByRole('heading',{name:heading,exact:true,level:1})).toBeVisible();
 }
 expect(errors).toEqual([]);
});
test('member creation, attendance, persistence and notification dry run',async({page})=>{
 await login(page);await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('[data-new="members"]').click();
 await page.getByLabel('Full name',{exact:true}).fill('E2E Member');await page.getByLabel('Phone (international format)').fill('+233201234567');await page.getByLabel('Member has consented to WhatsApp messages').check();
 await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.getByRole('cell',{name:'E2E Member',exact:false})).toBeVisible();
 await page.getByRole('button',{name:'Attendance',exact:true}).click();await page.getByRole('button',{name:'Mark all present'}).click();await page.getByRole('combobox',{name:'Attendance for E2E Member',exact:true}).selectOption('Absent');
 await page.getByRole('button',{name:'Save attendance',exact:true}).click();await expect(page.locator('#toast')).toContainText('Saved attendance');await page.reload();await page.getByRole('button',{name:'Attendance',exact:true}).click();await expect(page.getByRole('combobox',{name:'Attendance for E2E Member',exact:true})).toHaveValue('Absent');
 await page.getByRole('button',{name:'WhatsApp',exact:true}).click();await page.locator('#compose-message').click();await page.locator('select[name="member_ids"]').selectOption({label:'E2E Member · +233201234567'});await page.getByRole('button',{name:'Queue messages',exact:true}).click();
 await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('tbody tr').filter({hasText:'E2E Member'})).toContainText('queued');await page.getByRole('button',{name:'Process queue',exact:true}).click();await expect(page.locator('tbody tr').filter({hasText:'E2E Member'})).toContainText('dry_run');
});
test('teacher sees only assigned class and can save attendance',async({page})=>{
 await login(page,'teacher@ssms.local');await expect(page.getByRole('button',{name:'People & roles',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'WhatsApp',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Attendance',exact:true}).click();await expect(page.locator('#attendance-class option')).toHaveCount(1);await expect(page.locator('#attendance-class')).toHaveValue('1');
 await page.getByRole('button',{name:'Mark all present'}).click();await page.getByRole('button',{name:'Save attendance'}).click();await expect(page.locator('#toast')).toContainText('Saved attendance');
});
test('mobile navigation and member dialog remain usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await login(page);await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('[data-new="members"]').click();await expect(page.getByLabel('Full name',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Cancel',exact:true}).click();const layout=await page.evaluate(()=>({width:window.innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>window.innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,class:e.className,right:e.getBoundingClientRect().right}))}));expect(layout.scroll,JSON.stringify(layout)).toBeLessThanOrEqual(layout.width);
});

test('whole-class contributions, zero edit and printable quarter register',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Class contributions',exact:true}).click();await page.locator('[data-new="offerings"]').click();
 await page.getByLabel('Sabbath date',{exact:true}).fill('2026-09-19');await page.getByLabel('Amount',{exact:true}).fill('123.45');await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('tbody')).toContainText('123.45');
 await page.locator('[data-new="offerings"]').click();await page.getByLabel('Sabbath date',{exact:true}).fill('2026-09-19');await page.getByLabel('Amount',{exact:true}).fill('20');await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#dialog-error')).toContainText('already has a contribution');await page.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.locator('[data-edit^="offerings:"]').click();await page.getByLabel('Amount',{exact:true}).fill('0');await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await page.locator('[data-edit^="offerings:"]').click();await expect(page.getByLabel('Amount',{exact:true})).toHaveValue('0');await page.getByRole('button',{name:'Cancel',exact:true}).click();
 const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export contributions CSV'}).click();const download=await downloadPromise;expect(download.suggestedFilename()).toBe('ssms-contributions.csv');
 await page.getByRole('button',{name:'Quarterly contribution register'}).click();await page.locator('#register-year').fill('2026');await page.locator('#register-quarter').selectOption('3');await page.getByRole('button',{name:'View register',exact:true}).click();await expect(page.locator('.quarter-register')).toContainText('0.00');await expect(page.locator('.quarter-register')).toContainText('TOTAL (recorded)');
 await page.emulateMedia({media:'print'});await page.pdf({path:testInfo.outputPath('quarter-register.pdf'),format:'A4',landscape:true,printBackground:true});await page.emulateMedia({media:'screen'});
 await page.screenshot({path:testInfo.outputPath('class-contributions.png'),fullPage:true});
});

test('teacher quarterly book request and staff tracking',async({page},testInfo)=>{
 await login(page,'teacher@ssms.local');await expect(page.getByRole('button',{name:'Class contributions',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Annual report',exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'Book orders',exact:true}).click();await page.locator('[data-new="bookorders"]').click();await expect(page.locator('select[name="class_id"] option')).toHaveCount(1);await page.getByLabel('Book / edition').fill('E2E Quarterly Guide');await page.getByLabel('Quantity',{exact:true}).fill('12');await expect(page.getByLabel('Order status').locator('option')).toHaveCount(2);await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('tbody')).toContainText('E2E Quarterly Guide');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await login(page);await page.getByRole('button',{name:'Book orders',exact:true}).click();await page.locator('[data-edit^="bookorders:"]').click();await page.getByLabel('Order status').selectOption('Ordered');await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('tbody')).toContainText('Ordered');await page.screenshot({path:testInfo.outputPath('book-orders.png'),fullPage:true});
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await login(page,'teacher@ssms.local');await page.getByRole('button',{name:'Book orders',exact:true}).click();await expect(page.locator('[data-edit^="bookorders:"]')).toHaveCount(0);await expect(page.locator('tbody')).toContainText('Staff tracking');
});

test('reusable weekly programme and honest WhatsApp assignment queue',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('[data-new="members"]').click();await page.getByLabel('Full name',{exact:true}).fill('Programme Facilitator');await page.getByLabel('Phone (international format)').fill('+233201234568');await page.getByLabel('Member has consented to WhatsApp messages').check();await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();
 const next=new Date();next.setUTCDate(next.getUTCDate()+((6-next.getUTCDay()+7)%7||7));const sabbath=next.toISOString().slice(0,10);
 await page.getByRole('button',{name:'Weekly programme',exact:true}).click();await page.getByRole('button',{name:'Edit reusable template'}).click();await expect(page.locator('.programme-item')).toHaveCount(14);await page.locator('select[name="members_0"]').selectOption({label:'Programme Facilitator'});await page.getByRole('button',{name:'Save template',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();
 await page.locator('#programme-new-day').fill(sabbath);await page.getByRole('button',{name:'Create week from template'}).click();await expect(page.locator('.programme-sheet')).toContainText('Programme Facilitator');await expect(page.locator('.programme-sheet tbody tr')).toHaveCount(14);
 await page.getByRole('button',{name:'Edit reusable template'}).click();await page.locator('input[name="label_0"]').fill('Changed future template opening');await page.getByRole('button',{name:'Save template',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('.programme-sheet')).toContainText('Into My Heart / prayer');
 await page.getByRole('button',{name:'Preview WhatsApp assignments'}).click();await expect(page.locator('#editor')).toContainText('Dry run');await expect(page.locator('#assignment-previews')).toContainText('draft');await expect(page.getByRole('textbox',{name:'Assignment message for Programme Facilitator'})).toHaveValue(new RegExp(sabbath+'.*Into My Heart'));
 await page.getByRole('button',{name:'Queue dry-run assignments',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('#toast')).toContainText('Queued 1');await page.getByRole('button',{name:'Preview WhatsApp assignments'}).click();await expect(page.locator('#assignment-previews')).toContainText('queued');await page.getByRole('button',{name:'Queue dry-run assignments',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('#toast')).toContainText('already queued 1');
 await page.getByRole('button',{name:'WhatsApp',exact:true}).click();await page.getByRole('button',{name:'Process queue',exact:true}).click();await expect(page.locator('tbody tr').filter({hasText:'sabbath_programme_assignment'})).toContainText('dry_run');
 await page.getByRole('button',{name:'Weekly programme',exact:true}).click();await page.screenshot({path:testInfo.outputPath('weekly-programme.png'),fullPage:true});await page.getByRole('button',{name:'Preview WhatsApp assignments'}).click();await expect(page.locator('#assignment-previews')).toContainText('dry_run');await page.screenshot({path:testInfo.outputPath('assignment-preview.png'),fullPage:true});
});

test('annual report privacy, empty year, export and print',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Annual report',exact:true}).click();await expect(page.locator('h1')).toContainText('Sabbath School annual report');await expect(page.locator('.annual-report')).toContainText('Weekly Sabbath School programme');await expect(page.locator('.annual-report')).not.toContainText('E2E Member');await expect(page.locator('.annual-report')).not.toContainText('+233201234567');
 const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export annual CSV'}).click();expect((await downloadPromise).suggestedFilename()).toBe('ssms-annual.csv');await page.screenshot({path:testInfo.outputPath('annual-report.png'),fullPage:true});
 await page.emulateMedia({media:'print'});await page.pdf({path:testInfo.outputPath('annual-report.pdf'),format:'A4',printBackground:true});await expect(page.locator('#annual-year')).not.toBeVisible();await page.emulateMedia({media:'screen'});
 await page.locator('#annual-year').fill('2002');await page.getByRole('button',{name:'View year',exact:true}).click();await expect(page.locator('h1')).toContainText('2002');await expect(page.locator('.annual-report')).toContainText('No attendance records are available');
 await page.setViewportSize({width:390,height:844});for(const nav of ['Weekly programme','Book orders','Class contributions','Annual report']){await page.getByRole('button',{name:nav,exact:true}).click();if(nav==='Annual report')await expect(page.locator('.annual-report')).toBeVisible();const dimensions=await page.evaluate(()=>({w:innerWidth,s:document.documentElement.scrollWidth}));expect(dimensions.s,nav).toBeLessThanOrEqual(dimensions.w)}
});

test('reviewed roster import preserves unknown dates and skips duplicates',async({page})=>{
 await login(page);await page.getByRole('button',{name:'Classes',exact:true}).click();await page.locator('[data-new="classes"]').click();await page.getByLabel('Class name',{exact:true}).fill('Synthetic import class');await page.getByLabel('Class number / code').fill('99');await page.locator('select[name="teacher_id"]').selectOption('');await page.getByRole('button',{name:'Save class',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();
 await page.getByRole('button',{name:'Members',exact:true}).click();await page.getByRole('button',{name:'Import reviewed roster',exact:true}).click();await page.locator('select[name="class_id"]').selectOption({label:'Synthetic import class'});await page.getByLabel('Reviewed roster CSV').fill('name,residence,phone_local,class_office,notes\nSynthetic Imported Member,Example area,0201234577,H.T,Unknown join date');await page.getByRole('button',{name:'Preview roster import',exact:true}).click();await expect(page.locator('#editor')).toContainText('1 new members');await page.getByRole('button',{name:'Import reviewed members',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('#toast')).toContainText('Imported 1');
 await page.getByRole('button',{name:'Import reviewed roster',exact:true}).click();await page.locator('select[name="class_id"]').selectOption({label:'Synthetic import class'});await page.getByLabel('Reviewed roster CSV').fill('name,residence,phone_local,class_office,notes\nSynthetic Imported Member,Example area,0201234577,H.T,Unknown join date');await page.getByRole('button',{name:'Preview roster import',exact:true}).click();await expect(page.locator('#editor')).toContainText('0 new members, 1 exact duplicates');await page.getByRole('button',{name:'Import reviewed members',exact:true}).click();await expect(page.locator('#editor')).not.toBeVisible();
 const row=page.locator('tbody tr').filter({hasText:'Synthetic Imported Member'});await row.locator('[data-edit]').click();await expect(page.getByLabel('Phone as printed (optional)')).toHaveValue('0201234577');await expect(page.getByLabel('Join date unknown (exclude from annual join counts)')).toBeChecked();await expect(page.getByLabel('Member has consented to WhatsApp messages')).not.toBeChecked();
});


test('dropdown popup has visible options and works with mouse and keyboard',async({page},testInfo)=>{
 await login(page);await page.screenshot({path:testInfo.outputPath('readable-dashboard.png'),fullPage:true});
 await page.getByRole('button',{name:'Book orders',exact:true}).click();const status=page.locator('#order-status');
 const custom=await page.evaluate(()=>CSS.supports('appearance','base-select'));
 if(custom){
  await status.click();const ordered=page.getByRole('option',{name:'Ordered',exact:true});await expect(ordered).toBeVisible();await page.getByRole('option',{name:'Received',exact:true}).hover();
  await page.screenshot({path:testInfo.outputPath('readable-dropdown.png'),fullPage:true});await ordered.click();await expect(status).toHaveValue('Ordered');
  await status.focus();await page.keyboard.press('Space');await expect(page.getByRole('option',{name:'Ordered',exact:true})).toBeVisible();await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');await expect(status).toHaveValue('Requested');
  await status.focus();await page.keyboard.press('Space');await page.keyboard.press('Escape');await expect(status).toHaveValue('Requested');
 }else{await status.selectOption('Ordered');await expect(status).toHaveValue('Ordered')}
 await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('[data-new="members"]').click();await page.getByLabel('Full name',{exact:true}).fill('Unsaved preview');await page.getByLabel('Class office (printed label)').selectOption('H.T');await expect(page.getByRole('button',{name:'Save record',exact:true})).toBeInViewport();await page.screenshot({path:testInfo.outputPath('readable-member-form.png'),fullPage:true});await page.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Book orders',exact:true}).click();await page.locator('#order-status').selectOption('');await expect(page.getByRole('button',{name:'Book orders',exact:true})).toBeInViewport({ratio:0.99});const dimensions=await page.evaluate(()=>({w:innerWidth,s:document.documentElement.scrollWidth}));expect(dimensions.s).toBeLessThanOrEqual(dimensions.w);await page.screenshot({path:testInfo.outputPath('readable-mobile.png'),fullPage:true});
});

test('required fields, helpful error cards and saving feedback',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('[data-new="members"]').click();
 await expect(page.locator('#record-form .form-guidance')).toContainText('Required');
 await expect(page.getByLabel('Full name',{exact:true})).toHaveAttribute('aria-required','true');
 await expect(page.getByLabel('Residence',{exact:true})).not.toHaveAttribute('aria-required','true');
 await page.getByLabel('Email',{exact:true}).fill('incorrect-email');await page.getByRole('button',{name:'Save record',exact:true}).click();
 await expect(page.locator('#dialog-error')).toContainText('Please check your entries');await expect(page.getByLabel('Full name',{exact:true})).toHaveAttribute('aria-invalid','true');
 await expect(page.locator('.field-error')).toHaveCount(2);await page.screenshot({path:testInfo.outputPath('required-fields-errors.png')});
 await page.getByLabel('Full name',{exact:true}).fill('Feedback Test Member');await page.getByLabel('Email',{exact:true}).fill('');
 await expect(page.locator('.field-error')).toHaveCount(0);
 await page.route('**/api/members',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'internal failure'})}),{times:1});
 await page.getByRole('button',{name:'Save record',exact:true}).click();await expect(page.locator('#dialog-error')).toContainText('temporarily unavailable');
 await expect(page.locator('#dialog-error .error-body strong')).toContainText('complete this action');await expect(page.getByLabel('Full name',{exact:true})).toHaveValue('Feedback Test Member');
 let release;const gate=new Promise(resolve=>release=resolve);
 await page.route('**/api/members',async route=>{await gate;await route.continue()},{times:1});
 await page.getByRole('button',{name:'Save record',exact:true}).click();
 await expect(page.getByRole('button',{name:'Save record',exact:true})).toHaveAttribute('aria-busy','true');await expect(page.locator('#request-loader')).toBeVisible();
 await expect(page.getByRole('button',{name:'Save record',exact:true})).toContainText('Saving');await page.screenshot({path:testInfo.outputPath('saving-loader.png')});
 release();await expect(page.locator('#editor')).not.toBeVisible();await expect(page.locator('#request-loader')).toBeHidden();await expect(page.locator('tbody')).toContainText('Feedback Test Member');
});

test('initial connection failure shows a retry card instead of a blank page',async({page})=>{
 await page.route('**/api/state',route=>route.abort(),{times:1});await page.goto('/');await expect(page.getByRole('heading',{name:'Unable to open your workspace'})).toBeVisible();
 await expect(page.locator('.startup-card .error')).toContainText('Check your connection');await page.getByRole('button',{name:'Try again',exact:true}).click();await expect(page.getByRole('heading',{name:'Sign in to Sabbath School'})).toBeVisible();
 await expect(page.getByLabel('Email address',{exact:true})).toHaveAttribute('aria-required','true');
 await page.getByLabel('Email address',{exact:true}).fill('admin@ssms.local');await page.getByLabel('Password',{exact:true}).fill('incorrect-test-password');await page.getByRole('button',{name:'Sign in →',exact:true}).click();
 await expect(page.locator('#login-error .error-body')).toContainText('Email or password is incorrect');await expect(page.getByRole('button',{name:'Sign in →',exact:true})).toBeEnabled();
 await page.route('**/api/login',route=>route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({error:'Too many attempts. Try again in 15 minutes.'})}),{times:1});await page.getByRole('button',{name:'Sign in →',exact:true}).click();await expect(page.locator('#login-error')).toContainText('15 minutes');await expect(page.getByRole('button',{name:'Sign in →',exact:true})).toBeEnabled();
});

test('search and class filters never overlap at narrow widths',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Members',exact:true}).click();
 for(const width of [390,610,768,1280]){
  await page.setViewportSize({width,height:900});await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('#search').focus();
  const rects=await page.evaluate(()=>{const a=document.querySelector('#search').getBoundingClientRect(),b=document.querySelector('#class-filter').getBoundingClientRect();return {separate:a.right+6<=b.left||a.bottom+6<=b.top||b.bottom+6<=a.top,width:innerWidth,scroll:document.documentElement.scrollWidth}});
  expect(rects.separate,`Search/filter overlap at ${width}px`).toBeTruthy();expect(rects.scroll).toBeLessThanOrEqual(rects.width);
 }
 await page.setViewportSize({width:610,height:900});await page.getByRole('button',{name:'Members',exact:true}).click();await page.locator('#search').fill('no-such-member-search');await expect(page.locator('tbody')).toContainText('No records match');await page.locator('#class-filter').selectOption('1');await expect(page.locator('#search')).toHaveValue('no-such-member-search');await expect(page.locator('tbody')).toContainText('No records match');await page.locator('#search').fill('');
 await page.screenshot({path:testInfo.outputPath('search-filter-spacing.png')});
});

test('current published lesson loads automatically and fails honestly',async({page},testInfo)=>{
 await login(page);await page.getByRole('button',{name:'Lesson study',exact:true}).click();
 await expect(page.locator('#automatic-lesson')).toContainText('Synthetic published week');await expect(page.getByRole('link',{name:'Read today’s study ↗',exact:true})).toHaveAttribute('href','https://absg.sspmadventist.org/en/2026-04/03/05');
 await expect(page.getByRole('link',{name:'Read this week’s lesson ↗',exact:true})).toHaveAttribute('rel','noopener noreferrer');await page.screenshot({path:testInfo.outputPath('automatic-current-lesson.png'),fullPage:true});
 await page.route('**/api/lessons/current',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({available:false,day:'2026-10-14',publisher_url:'https://absg.sspmadventist.org/this-week',message:'Current details are temporarily unavailable.'})}));
 await page.getByRole('button',{name:'Lesson study',exact:true}).click();await expect(page.locator('#automatic-lesson')).toContainText('temporarily unavailable');await expect(page.getByRole('link',{name:'Open the current study ↗',exact:true})).toHaveAttribute('href','https://absg.sspmadventist.org/this-week');await expect(page.locator('#automatic-lesson')).not.toContainText('Synthetic published week');
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
