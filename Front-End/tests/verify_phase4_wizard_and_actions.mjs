import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/Harsh Poshiya/.gemini/antigravity-ide/brain/6827506a-a41b-43b5-85cf-09b5cead5919';

const faculty1Session = {
  access: "mockTokenFaculty1",
  refresh: "mockTokenFaculty1",
  role: "faculty",
  user: { id: 101, first_name: "Pallavi", last_name: "Rajput", email: "pallavi.rajput@pits.example.edu", institution: { id: 1, name: "Pragyan Institute" } }
};

const faculty2Session = {
  access: "mockTokenFaculty2",
  refresh: "mockTokenFaculty2",
  role: "faculty",
  user: { id: 102, first_name: "Mohit", last_name: "Banerjee", email: "mohit.banerjee@pits.example.edu", institution: { id: 1, name: "Pragyan Institute" } }
};

const adminSession = {
  access: "mockTokenAdmin",
  refresh: "mockTokenAdmin",
  role: "admin",
  user: { id: 1, first_name: "Admin", last_name: "PITS", email: "admin.pits@example.edu", institution: { id: 1, name: "Pragyan Institute" } }
};

const mockFacultyList = [
  {
    id: 1,
    user_id: 101,
    full_name: "Dr. Pallavi Rajput",
    first_name: "Pallavi",
    last_name: "Rajput",
    email: "pallavi.rajput@pits.example.edu",
    employee_id: "FAC-2026-001",
    department: "Computer Science",
    designation: "Assistant Professor",
    is_active: true,
    status: "Active",
  },
  {
    id: 2,
    user_id: 102,
    full_name: "Prof. Mohit Banerjee",
    first_name: "Mohit",
    last_name: "Banerjee",
    email: "mohit.banerjee@pits.example.edu",
    employee_id: "FAC-2026-002",
    department: "Information Technology",
    designation: "Associate Professor",
    is_active: false,
    status: "Inactive",
  }
];

const mockStudentList = [
  {
    id: 1,
    user_id: 201,
    full_name: "Tarun Rathore",
    first_name: "Tarun",
    last_name: "Rathore",
    email: "tarun.rathore@pits.example.edu",
    roll_number: "PITS-CS-0001",
    department: "Computer Science",
    exams_attempted: 4,
    average_score: 82,
    highest_score: 94,
    lowest_score: 70,
    performance_status: "good",
    is_active: true,
    status: "Active",
  }
];

const mockDepartments = [
  { id: 1, department_name: "Computer Science" },
  { id: 2, department_name: "Information Technology" },
  { id: 3, department_name: "Mechanical Engineering" },
];

function setupApiRoutes(page, session) {
  // Auto accept confirm/alert dialogs
  page.on('dialog', async (dialog) => {
    console.log(`  Accepting dialog: [${dialog.type()}] "${dialog.message()}"`);
    await dialog.accept();
  });

  // Default catch-all for other api calls (registered first so specific routes override it)
  page.route('**/api/**', async (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: {} }) });
  });

  // Intercept Auth
  page.route('**/api/auth/me**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', role: session?.role || 'admin', user: session?.user || adminSession.user }),
    });
  });

  // Route mocking for faculty endpoints (both /api/admin/faculty and /api/admins/faculty)
  page.route(/.*\/api\/admin(s)?\/faculty.*/, async (route) => {
    const req = route.request();
    const url = req.url();
    const method = req.method();

    if (url.includes('/reset-password') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'Password reset successfully',
          data: { new_password: 'GeneratedPass@2026!' }
        })
      });
    }

    if (method === 'GET' && url.match(/\/faculty\/1(\?|\/|$)/)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: mockFacultyList[0]
        })
      });
    }

    if (method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: mockFacultyList,
          results: mockFacultyList,
          count: mockFacultyList.length,
          pagination: { total_items: 2, total_pages: 1, current_page: 1, page_size: 10 }
        })
      });
    }

    return route.continue();
  });

  // Route mocking for student endpoints (both /api/admin/students and /api/admins/students)
  page.route(/.*\/api\/admin(s)?\/students.*/, async (route) => {
    const req = route.request();
    const url = req.url();
    const method = req.method();

    if (url.includes('/reset-password') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'Student password reset successfully',
          data: { new_password: 'StudentReset@2026!' }
        })
      });
    }

    if (method === 'GET' && url.match(/\/students\/1(\?|\/|$)/)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: mockStudentList[0]
        })
      });
    }

    if (method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: mockStudentList,
          results: mockStudentList,
          count: mockStudentList.length,
          pagination: { total_items: 1, total_pages: 1, current_page: 1, page_size: 10 }
        })
      });
    }

    return route.continue();
  });

  page.route(/.*\/change-department(\/.*)?$/, async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        message: 'Department successfully changed',
        data: { department: 'Information Technology' }
      })
    });
  });

  page.route(/.*\/departments(\/.*)?$/, async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: mockDepartments
      })
    });
  });

  page.route(/.*\/institution(\/.*)?$/, async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: { departments: mockDepartments }
      })
    });
  });

  page.route('**/api/faculty/profile/**', async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: {
          id: 1,
          department: "Computer Science",
          designation: "Assistant Professor",
          employee_id: "FPITCS01"
        }
      })
    });
  });
}

async function runVerification() {
  console.log("=== STARTING PHASE 4 VERIFICATION SUITE ===");
  const browser = await chromium.launch({ headless: true });

  // -------------------------------------------------------------
  // PART A: FACULTY TESTS (Wizard Clean State, Draft, Isolation)
  // -------------------------------------------------------------
  const facultyCtx = await browser.newContext();
  await facultyCtx.addInitScript((sess) => {
    sessionStorage.setItem('exam_ai_auth', JSON.stringify(sess));
  }, faculty1Session);

  const page = await facultyCtx.newPage();
  setupApiRoutes(page, faculty1Session);

  // TEST 1: Faculty Wizard Fresh State & Zero Pre-filled Old Data
  console.log("\n[TEST 1] Testing Faculty Wizard Fresh State (User 101)...");
  await page.goto('http://127.0.0.1:3000/faculty/generate');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForSelector('input[placeholder*="Computer Networks"]');

  const titleVal = await page.locator('input[placeholder*="Computer Networks"]').inputValue();
  const subjectVal = await page.locator('input[placeholder*="CS-402"]').inputValue();
  console.log(`  Initial Title: "${titleVal}" (Expected: "")`);
  console.log(`  Initial Subject: "${subjectVal}" (Expected: "")`);
  if (titleVal !== "" || subjectVal !== "") {
    throw new Error(`TEST 1 FAILED: Wizard Step 1 was prefilled! Title="${titleVal}", Subject="${subjectVal}"`);
  }

  const startsAtVal = await page.locator('input[type="datetime-local"]').first().inputValue();
  console.log(`  Default startsAt: ${startsAtVal}`);
  const startsAtDate = new Date(startsAtVal);
  if (isNaN(startsAtDate.getTime()) || startsAtDate.getTime() < Date.now() - 60000) {
    throw new Error(`TEST 1 FAILED: Default startsAt is invalid or in the past: ${startsAtVal}`);
  }
  console.log("  ✓ TEST 1 PASSED: Wizard starts completely fresh with future schedule.");

  // TEST 2: Autosave, Draft Detection Banner, and Resume Draft
  console.log("\n[TEST 2] Testing Autosave & Scoped Draft Recovery...");
  await page.locator('input[placeholder*="Computer Networks"]').fill("Mid Term Test 2026");
  await page.locator('input[placeholder*="CS-402"]').fill("Distributed Systems");
  await page.waitForTimeout(800);

  const draftInStorage = await page.evaluate(() => localStorage.getItem('wizard:draft:101'));
  console.log(`  Storage key wizard:draft:101 exists: ${!!draftInStorage}`);
  if (!draftInStorage || !draftInStorage.includes("Mid Term Test 2026")) {
    throw new Error(`TEST 2 FAILED: Draft was not saved in wizard:draft:101! Got: ${draftInStorage}`);
  }

  await page.reload();
  await page.waitForLoadState('domcontentloaded');
  await page.waitForSelector('text=Unfinished Draft Available');

  const bannerText = await page.locator('text=Unfinished Draft Available').textContent();
  console.log(`  Banner detected: "${bannerText.trim()}"`);
  if (!bannerText) {
    throw new Error("TEST 2 FAILED: Draft detection banner was not shown after reload!");
  }

  await page.click('button:has-text("Resume Draft")');
  await page.waitForTimeout(300);

  const restoredTitle = await page.locator('input[placeholder*="Computer Networks"]').inputValue();
  const restoredSubject = await page.locator('input[placeholder*="CS-402"]').inputValue();
  console.log(`  Restored Title: "${restoredTitle}", Subject: "${restoredSubject}"`);
  if (restoredTitle !== "Mid Term Test 2026" || restoredSubject !== "Distributed Systems") {
    throw new Error(`TEST 2 FAILED: Resume draft did not restore fields properly!`);
  }
  console.log("  ✓ TEST 2 PASSED: Autosave and Draft Resume work perfectly.");

  // TEST 3: Reset Form Button & Cleanup
  console.log("\n[TEST 3] Testing Reset Form button...");
  await page.click('button:has-text("Reset Form")');
  await page.waitForTimeout(400);

  const resetTitle = await page.locator('input[placeholder*="Computer Networks"]').inputValue();
  const resetSubject = await page.locator('input[placeholder*="CS-402"]').inputValue();
  const draftAfterReset = await page.evaluate(() => localStorage.getItem('wizard:draft:101'));
  console.log(`  Title after reset: "${resetTitle}", Storage after reset: ${draftAfterReset}`);
  if (resetTitle !== "" || draftAfterReset !== null) {
    throw new Error("TEST 3 FAILED: Reset Form button did not clear inputs or localStorage draft!");
  }
  console.log("  ✓ TEST 3 PASSED: Reset Form button completely cleared wizard state and storage.");

  // TEST 4: Cross-User Draft Isolation
  console.log("\n[TEST 4] Testing Cross-User Draft Isolation...");
  await page.locator('input[placeholder*="Computer Networks"]').fill("Faculty 1 Private Draft");
  await page.waitForTimeout(800);

  // User 102 context
  const faculty2Ctx = await browser.newContext();
  await faculty2Ctx.addInitScript((sess) => {
    sessionStorage.setItem('exam_ai_auth', JSON.stringify(sess));
  }, faculty2Session);
  const pageF2 = await faculty2Ctx.newPage();
  setupApiRoutes(pageF2, faculty2Session);

  await pageF2.goto('http://127.0.0.1:3000/faculty/generate');
  await pageF2.waitForLoadState('domcontentloaded');
  await pageF2.waitForSelector('input[placeholder*="Computer Networks"]');

  const bannerForFaculty2 = await pageF2.locator('text=Unfinished Draft Available').count();
  const f2Title = await pageF2.locator('input[placeholder*="Computer Networks"]').inputValue();
  console.log(`  Faculty 2 draft banner count: ${bannerForFaculty2}, Title: "${f2Title}"`);
  if (bannerForFaculty2 > 0 || f2Title !== "") {
    throw new Error("TEST 4 FAILED: Cross-user draft leakage! Faculty 2 saw Faculty 1's draft.");
  }
  console.log("  ✓ TEST 4 PASSED: User drafts are strictly isolated by userId.");

  // Wizard screenshot
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: path.join(ARTIFACT_DIR, 'phase4_faculty_wizard_clean.png') });

  await facultyCtx.close();
  await faculty2Ctx.close();

  // -------------------------------------------------------------
  // PART B: ADMIN TESTS (Redesigned Actions, Modals, Zero Scroll)
  // -------------------------------------------------------------
  const adminCtx = await browser.newContext();
  await adminCtx.addInitScript((sess) => {
    sessionStorage.setItem('exam_ai_auth', JSON.stringify(sess));
  }, adminSession);
  const adminPage = await adminCtx.newPage();
  setupApiRoutes(adminPage, adminSession);

  console.log("\n[TEST 5] Testing Admin > Faculty Actions (Primary View + '⋯' Dropdown)...");
  await adminPage.goto('http://127.0.0.1:3000/admin/faculty');
  await adminPage.waitForLoadState('domcontentloaded');
  await adminPage.waitForTimeout(2000);
  console.log("  adminPage current URL:", adminPage.url());
  const bodyText = await adminPage.evaluate(() => document.body.innerText);
  console.log("  adminPage snippet:", bodyText.replace(/\n+/g, ' ').slice(0, 300));
  await adminPage.waitForSelector('button:has-text("View")');

  // Check Primary "View" button
  const viewBtnCount = await adminPage.locator('button:has-text("View")').count();
  console.log(`  Primary View buttons found: ${viewBtnCount}`);
  if (viewBtnCount === 0) {
    throw new Error("TEST 5 FAILED: Primary 'View' button not found on Admin Faculty page!");
  }

  // Click View button to open details modal
  await adminPage.locator('button:has-text("View")').first().click();
  await adminPage.waitForTimeout(400);
  const modalHeader = await adminPage.locator('h3:has-text("Faculty Details")').count();
  console.log(`  Faculty Details modal opened: ${modalHeader > 0}`);
  if (modalHeader === 0) {
    throw new Error("TEST 5 FAILED: Clicking View button did not open Faculty Details modal!");
  }
  // Click Close button
  await adminPage.locator('button:has-text("Close")').click();
  await adminPage.waitForTimeout(400);

  // Check single "⋯" dropdown button
  const moreActionsBtn = adminPage.locator('button[aria-label="More actions for Dr. Pallavi Rajput"]');
  const moreBtnCount = await moreActionsBtn.count();
  console.log(`  More actions '⋯' buttons found: ${moreBtnCount}`);
  if (moreBtnCount === 0) {
    throw new Error("TEST 5 FAILED: '⋯' more actions button not found!");
  }

  // Click '⋯' button to open dropdown
  await moreActionsBtn.first().click();
  await adminPage.waitForTimeout(300);

  // Verify dropdown items
  const hasEdit = await adminPage.locator('[role="menuitem"]:has-text("Edit Details")').count();
  const hasEmail = await adminPage.locator('[role="menuitem"]:has-text("Email Faculty")').count();
  const hasChangeDept = await adminPage.locator('[role="menuitem"]:has-text("Change Department")').count();
  const hasResetPwd = await adminPage.locator('[role="menuitem"]:has-text("Reset Password")').count();
  const hasDeactivate = await adminPage.locator('[role="menuitem"]:has-text("Deactivate Account")').count();
  const hasDelete = await adminPage.locator('[role="menuitem"]:has-text("Delete Faculty")').count();

  console.log(`  Dropdown items: Edit=${hasEdit}, Email=${hasEmail}, ChangeDept=${hasChangeDept}, ResetPwd=${hasResetPwd}, Deactivate=${hasDeactivate}, Delete=${hasDelete}`);
  if (!hasEdit || !hasEmail || !hasChangeDept || !hasResetPwd || !hasDeactivate || !hasDelete) {
    throw new Error("TEST 5 FAILED: Dropdown menu missing expected professional actions!");
  }

  // Test "Change Department" modal
  console.log("  Testing Change Department modal...");
  await adminPage.locator('[role="menuitem"]:has-text("Change Department")').click();
  await adminPage.waitForTimeout(400);
  const deptModalHeader = await adminPage.locator('h3:has-text("Change Department")').count();
  if (deptModalHeader === 0) {
    throw new Error("TEST 5 FAILED: Change Department modal did not open!");
  }
  await adminPage.locator('button:has-text("Cancel")').click();
  await adminPage.waitForTimeout(400);

  // Test "Reset Password" modal
  console.log("  Testing Reset Password modal...");
  await moreActionsBtn.first().click();
  await adminPage.waitForTimeout(300);
  await adminPage.locator('[role="menuitem"]:has-text("Reset Password")').click();
  await adminPage.waitForTimeout(400);
  const pwdModalHeader = await adminPage.locator('h3:has-text("Reset Password")').count();
  if (pwdModalHeader === 0) {
    throw new Error("TEST 5 FAILED: Reset Password modal did not open!");
  }
  // Click Generate Random button
  await adminPage.locator('button:has-text("Generate Random")').click();
  await adminPage.waitForTimeout(200);
  const genPassInput = await adminPage.locator('input[placeholder*="Leave blank"]').inputValue();
  console.log(`  Auto-generated password in modal: "${genPassInput}"`);
  if (!genPassInput || genPassInput.length < 10) {
    throw new Error("TEST 5 FAILED: Reset Password modal did not generate secure password!");
  }
  await adminPage.locator('button:has-text("Cancel")').click();
  await adminPage.waitForTimeout(400);
  console.log("  ✓ TEST 5 PASSED: Primary View + Dropdown Actions and Modals work flawlessly.");

  // TEST 6: Admin Students Mirroring
  console.log("\n[TEST 6] Testing Admin > Students Actions Mirroring...");
  await adminPage.goto('http://127.0.0.1:3000/admin/students');
  await adminPage.waitForLoadState('domcontentloaded');
  await adminPage.waitForTimeout(2000);
  console.log("  adminPage students URL:", adminPage.url());
  const stuBody = await adminPage.evaluate(() => document.body.innerText);
  console.log("  adminPage students snippet:", stuBody.replace(/\n+/g, ' ').slice(0, 300));
  await adminPage.waitForSelector('button:has-text("View")');

  const studentViewBtnCount = await adminPage.locator('button:has-text("View")').count();
  const studentMoreBtnCount = await adminPage.locator('button[aria-label*="More actions"]').count();
  console.log(`  Admin Students View buttons: ${studentViewBtnCount}, More buttons: ${studentMoreBtnCount}`);
  if (studentViewBtnCount === 0 || studentMoreBtnCount === 0) {
    throw new Error("TEST 6 FAILED: Admin Students does not mirror the hybrid actions pattern!");
  }
  console.log("  ✓ TEST 6 PASSED: Admin Students mirrors the professional pattern.");

  // TEST 7: Zero Horizontal Scrollbar Check Across Viewports
  console.log("\n[TEST 7] Testing Zero Horizontal Scrollbar on Admin Faculty & Students...");
  const viewports = [
    { width: 1500, height: 900, name: "1500px" },
    { width: 1280, height: 800, name: "1280px" },
    { width: 1024, height: 768, name: "1024px" },
    { width: 768, height: 1024, name: "768px" },
    { width: 375, height: 667, name: "375px" },
  ];

  for (const vp of viewports) {
    await adminPage.setViewportSize({ width: vp.width, height: vp.height });
    await adminPage.goto('http://127.0.0.1:3000/admin/faculty');
    await adminPage.waitForLoadState('domcontentloaded');
    await adminPage.waitForTimeout(300);

    const scrollCheck = await adminPage.evaluate(() => {
      const docScroll = document.documentElement.scrollWidth > document.documentElement.clientWidth;
      const bodyScroll = document.body.scrollWidth > document.body.clientWidth;
      const tableWrapper = document.querySelector('.overflow-x-hidden') || document.querySelector('table')?.parentElement;
      const wrapperScroll = tableWrapper ? tableWrapper.scrollWidth > tableWrapper.clientWidth : false;
      return { docScroll, bodyScroll, wrapperScroll };
    });

    console.log(`  Viewport ${vp.name}: docScroll=${scrollCheck.docScroll}, bodyScroll=${scrollCheck.bodyScroll}, wrapperScroll=${scrollCheck.wrapperScroll}`);
    if (scrollCheck.docScroll || scrollCheck.bodyScroll || scrollCheck.wrapperScroll) {
      throw new Error(`TEST 7 FAILED: Horizontal scrollbar detected at ${vp.name}!`);
    }

    const screenshotPath = path.join(ARTIFACT_DIR, `phase4_admin_faculty_${vp.name}.png`);
    await adminPage.screenshot({ path: screenshotPath, fullPage: false });
  }

  await adminCtx.close();
  await browser.close();
  console.log("\n=== ALL 7 TESTS PASSED SUCCESSFULLY! ===");
}

runVerification().catch((err) => {
  console.error("VERIFICATION FAILED:", err);
  process.exit(1);
});
