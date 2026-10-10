const {test,expect}=require('@playwright/test');
async function login(page,email='admin@ssms.local'){
 await page.goto('/');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(process.env.SSMS_DEMO_PASSWORD);
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
