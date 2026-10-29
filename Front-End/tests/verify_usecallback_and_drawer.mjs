import { chromium } from 'playwright';
import { spawn } from 'child_process';
import http from 'http';
import path from 'path';
import fs from 'fs';

const PORT = 3288;
const BASE_URL = `http://127.0.0.1:${PORT}`;

const mockAdminSession = {
  access: "mockAdminToken",
  refresh: "mockAdminRefresh",
  role: "admin",
  user: {
    id: 1,
    first_name: "Admin",
    last_name: "User",
    email: "admin@test.edu",
    institution: { id: 1, name: "Test Institute" }
  }
};

const mockFacultySession = {
  access: "mockFacultyToken",
  refresh: "mockFacultyRefresh",
  role: "faculty",
  user: {
    id: 2,
    first_name: "Faculty",
    last_name: "Member",
    email: "faculty@test.edu",
    department: "Computer Science",
    institution: { id: 1, name: "Test Institute" }
  }
};

const mockStudentSession = {
  access: "mockStudentToken",
  refresh: "mockStudentRefresh",
  role: "student",
  user: {
    id: 3,
    first_name: "Alice",
    last_name: "Student",
    email: "student@test.edu",
    roll_number: "CS-2026-001",
    department: "Computer Science",
    institution: { id: 1, name: "Test Institute" }
  }
};

const mockSuperAdminSession = {
  access: "mockSuperAdminToken",
  refresh: "mockSuperAdminRefresh",
  role: "superadmin",
  user: {
    id: 99,
    first_name: "Super",
    last_name: "Admin",
    email: "superadmin@test.edu"
  }
};

const mockStudents = [
  {
    id: 1,
    full_name: "Alice Johnson",
    email: "alice@test.edu",
    roll_number: "CS-2026-001",
    department: "Computer Science",
    year: "2026",
    is_active: true,
    exams_attempted: 4,
    number_of_exams: 4,
    average_score: 84.5,
    highest_score: 95,
    lowest_score: 72,
    performance_status: "Excellent"
  },
  {
    id: 2,
    full_name: "Bob Smith",
    email: "bob@test.edu",
    roll_number: "CS-2026-002",
    department: "Computer Science",
    year: "2026",
    is_active: false,
    exams_attempted: 2,
    number_of_exams: 2,
    average_score: 55.0,
    highest_score: 60,
    lowest_score: 50,
    performance_status: "Average"
  }
];

const mockFacultyList = [
  {
    id: 1,
    full_name: "Dr. Evelyn Reed",
    email: "ereed@test.edu",
    employee_id: "FAC-001",
    department: "Computer Science",
    designation: "Associate Professor",
    is_active: true,
    status: "Active",
    exams_count: 5,
    recent_exams: []
  },
  {
    id: 2,
    full_name: "Prof. Arthur Dent",
    email: "adent@test.edu",
    employee_id: "FAC-002",
    department: "Computer Science",
    designation: "Lecturer",
    is_active: false,
    status: "Inactive",
    exams_count: 2,
    recent_exams: []
  }
];

function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      http.get(url, (res) => {
        resolve(true);
      }).on('error', () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Server at ${url} did not start within ${timeoutMs}ms`));
        } else {
          setTimeout(check, 250);
        }
      });
    };
    check();
  });
}

async function setupApiMocks(page, session) {
  await page.addInitScript((s) => {
    sessionStorage.setItem('exam_ai_auth', JSON.stringify(s));
    localStorage.setItem('exam_ai_auth', JSON.stringify(s));
  }, session);

  // Catch-all API fallback (registered first, overridden by specific routes below)
  await page.route(/\/api\//, async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: [] })
    });
  });

  // Student APIs
  await page.route(/\/api\/student\/exams/, async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([])
    });
  });

  await page.route(/\/api\/student\/performance/, async (route) => {
    const url = route.request().url();
    if (url.includes('/summary')) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            total_attempts: 0,
            overall_average: null,
            highest_score: null,
            lowest_score: null,
            pass_count: 0,
            fail_count: 0,
            pass_rate: null,
            last_exam_date: null,
            performance_status: "N/A",
            department: "Computer Science"
          }
        })
      });
    } else if (url.includes('/results')) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: [],
          pagination: {
            page: 1,
            page_size: 10,
            total_count: 0,
            total_pages: 1,
            has_next: false,
            has_prev: false
          }
        })
      });
    } else if (url.includes('/trend')) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: [] })
      });
    } else if (url.includes('/subjects')) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            subjects: [],
            strongest_subject: null,
            weakest_subject: null
          }
        })
      });
    } else {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: [] })
      });
    }
  });

  await page.route('**/api/auth/me/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', role: session.role, user: session.user })
    });
  });

  await page.route('**/api/departments/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', departments: ["Computer Science", "Information Technology"] })
    });
  });

  // Admin students endpoints
  await page.route(/\/api\/admin\/students/, async (route) => {
    const url = route.request().url();
    if (url.includes('/results')) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            student: mockStudents[0],
            summary: {
              total_attempts: 4,
              overall_average: 84.5,
              highest_score: 95,
              lowest_score: 72,
              performance_status: "Excellent"
            },
            results: [
              {
                id: 1,
                exam_id: 10,
                exam_title: "Data Structures Midterm",
                subject: "Computer Science",
                score: 88,
                total_marks: 100,
                percentage: 88,
                status: "graded",
                submitted_at: "2026-10-15T10:00:00Z"
              }
            ],
            trend: []
          }
        })
      });
      return;
    }

    const matchSingle = url.match(/\/api\/admin\/students\/(\d+)/);
    if (matchSingle) {
      const id = parseInt(matchSingle[1], 10);
      const student = mockStudents.find(s => s.id === id) || mockStudents[0];
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: student })
      });
      return;
    }

    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: mockStudents,
        results: mockStudents,
        count: mockStudents.length,
        total_count: mockStudents.length,
        total_pages: 1,
        page: 1,
        page_size: 10,
        stats: {
          total_students: mockStudents.length,
          overall_average_score: 75.0,
          top_performer: null,
          students_below_pass: 0
        }
      })
    });
  });

  // Admin faculty endpoints
  await page.route(/\/api\/admin\/faculty/, async (route) => {
    const url = route.request().url();
    const matchSingle = url.match(/\/api\/admin\/faculty\/(\d+)/);
    if (matchSingle) {
      const id = parseInt(matchSingle[1], 10);
      const fac = mockFacultyList.find(f => f.id === id) || mockFacultyList[0];
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: fac })
      });
      return;
    }

    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        data: mockFacultyList,
        results: mockFacultyList,
        count: mockFacultyList.length,
        total_count: mockFacultyList.length,
        total_pages: 1,
        page: 1,
        page_size: 10,
        stats: {
          total_faculty: mockFacultyList.length,
          active_faculty: 1,
          inactive_faculty: 1,
          total_departments: 1
        }
      })
    });
  });

  // Faculty AI models & generation
  await page.route('**/api/faculty/paper/models/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        models: [
          { name: "qwen2.5:3b-instruct", size_gb: 1.9, family: "qwen", is_recommended: true }
        ]
      })
    });
  });

  await page.route('**/api/faculty/profile/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'success', data: { department: "Computer Science" } })
    });
  });

  await page.route('**/api/faculty/generation/active-job/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ active_job: null })
    });
  });

  await page.route('**/api/faculty/question-bank/**', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        questions: [
          {
            id: 101,
            question_type: "mcq",
            text: "What is time complexity of binary search?",
            options: ["O(1)", "O(log n)", "O(n)", "O(n^2)"],
            correct_answer: "O(log n)",
            marks: 2,
            difficulty: "easy",
            topic: "Algorithms"
          },
          {
            id: 102,
            question_type: "short_answer",
            text: "Define polymorphism in OOP.",
            model_answer: "Ability of different types to respond to the same interface.",
            marks: 3,
            difficulty: "medium",
            topic: "OOP"
          }
        ]
      })
    });
  });
}

async function run() {
  console.log('--- Starting Part 3 Playwright Verification ---');

  console.log(`Starting Vite preview on port ${PORT}...`);
  const previewProcess = spawn(
    process.execPath,
    ['node_modules/vite/bin/vite.js', 'preview', '--port', String(PORT), '--host', '127.0.0.1'],
    {
      cwd: 'Front-End',
      stdio: 'ignore'
    }
  );

  let browser;
  let testErrors = [];

  try {
    await waitForServer(BASE_URL);
    console.log(`Preview server ready at ${BASE_URL}`);

    browser = await chromium.launch({ headless: true });

    // =========================================================================
    // TEST 1: FACULTY GENERATE PAPER PAGE (BUG 1 FIX VERIFICATION)
    // =========================================================================
    console.log('\n[TEST 1] Verifying Faculty Generate Paper Page (useCallback fix)...');
    {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await context.newPage();

      const pageErrors = [];
      const consoleErrors = [];

      page.on('pageerror', (err) => {
        console.error('Page error detected:', err.message);
        pageErrors.push(err.message);
      });

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          const text = msg.text();
          if (!text.includes('net::ERR_CONNECTION_REFUSED')) {
            console.error('Console error detected:', text);
            consoleErrors.push(text);
          }
        }
      });

      await setupApiMocks(page, mockFacultySession);
      await page.goto(`${BASE_URL}/faculty/generate`, { waitUntil: 'networkidle' });

      // Verify no runtime crash ("Unexpected Application Error! useCallback is not defined")
      const bodyText = await page.textContent('body');
      if (bodyText.includes('useCallback is not defined') || bodyText.includes('Unexpected Application Error')) {
        testErrors.push('FacultyGeneratePaper crashed with ReferenceError: useCallback is not defined');
      }

      // Verify Step 1 is rendered
      const titleInput = page.locator('input[placeholder*="Midterm Assessment"], input[placeholder*="Exam Title"], input[type="text"]').first();
      await titleInput.waitFor({ timeout: 5000 });
      console.log('✓ Step 1 rendered without crashes');

      // Test Question Bank mode switch which uses useCallback fetchBankQuestions
      const questionBankTab = page.locator('button:has-text("Question Bank")');
      if (await questionBankTab.count() > 0) {
        await questionBankTab.first().click();
        await page.waitForTimeout(500);
        console.log('✓ Question Bank mode switched and fetchBankQuestions hook invoked successfully');
      }

      if (pageErrors.length > 0) {
        testErrors.push(`TEST 1 Page errors: ${pageErrors.join(', ')}`);
      }
      if (consoleErrors.length > 0) {
        testErrors.push(`TEST 1 Console errors: ${consoleErrors.join(', ')}`);
      }

      await context.close();
    }

    // =========================================================================
    // TEST 2: ADMIN STUDENTS VIEW DRAWER (BUG 2 FIX VERIFICATION)
    // =========================================================================
    console.log('\n[TEST 2] Verifying Admin Students View Drawer (Single Close Button)...');
    {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await context.newPage();

      const pageErrors = [];
      page.on('pageerror', (err) => pageErrors.push(err.message));

      await setupApiMocks(page, mockAdminSession);
      await page.goto(`${BASE_URL}/admin/students`, { waitUntil: 'networkidle' });

      // Find the first View button in the table
      const viewButton = page.locator('button[aria-label^="View "]').first();
      await viewButton.waitFor({ state: 'visible', timeout: 5000 });
      await viewButton.click();

      // Wait for drawer SheetContent to open
      const sheetContent = page.locator('[data-slot="sheet-content"]');
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });

      // Check close buttons in the top-right header area
      // Exactly ONE close button with aria-label="Close" must exist
      const closeButtons = sheetContent.locator('button[aria-label="Close"]');
      const closeCount = await closeButtons.count();
      console.log(`Found ${closeCount} close button(s) in Admin Students View drawer`);

      if (closeCount !== 1) {
        testErrors.push(`Admin Students drawer has ${closeCount} close buttons (expected exactly 1)`);
      } else {
        console.log('✓ Exactly 1 close button confirmed in Admin Students drawer');
      }

      // Check aria-label and tooltip/title attribute
      const closeBtn = closeButtons.first();
      const ariaLabel = await closeBtn.getAttribute('aria-label');
      const titleAttr = await closeBtn.getAttribute('title');
      if (ariaLabel !== 'Close') {
        testErrors.push(`Close button missing aria-label="Close", got: ${ariaLabel}`);
      }
      if (!titleAttr) {
        testErrors.push(`Close button missing tooltip title attribute`);
      } else {
        console.log(`✓ Close button has aria-label="${ariaLabel}" and title="${titleAttr}"`);
      }

      // Test 2a: Close via clicking the close button
      await closeBtn.click();
      await sheetContent.waitFor({ state: 'hidden', timeout: 3000 });
      console.log('✓ Drawer closed cleanly via X button click');

      // Test 2b: Re-open and close with Escape key
      await viewButton.click();
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });
      await page.keyboard.press('Escape');
      await sheetContent.waitFor({ state: 'hidden', timeout: 3000 });
      console.log('✓ Drawer closed cleanly via Escape key');

      // Test 2c: Re-open and close with overlay click
      await viewButton.click();
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });
      const overlay = page.locator('[data-slot="sheet-overlay"]');
      await overlay.click({ position: { x: 10, y: 10 }, force: true });
      await sheetContent.waitFor({ state: 'hidden', timeout: 3000 });
      console.log('✓ Drawer closed cleanly via Overlay click');

      // Test 2d: Open via URL query parameter (?view=1)
      await page.goto(`${BASE_URL}/admin/students?view=1`, { waitUntil: 'networkidle' });
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });
      const urlCloseCount = await sheetContent.locator('button[aria-label="Close"]').count();
      if (urlCloseCount !== 1) {
        testErrors.push(`Admin Students drawer opened via URL has ${urlCloseCount} close buttons (expected 1)`);
      } else {
        console.log('✓ Admin Students drawer opened via URL has exactly 1 close button');
      }

      await context.close();
    }

    // =========================================================================
    // TEST 3: ADMIN FACULTY VIEW DRAWER (BUG 2 FIX VERIFICATION)
    // =========================================================================
    console.log('\n[TEST 3] Verifying Admin Faculty View Drawer (Single Close Button)...');
    {
      const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
      const page = await context.newPage();

      await setupApiMocks(page, mockAdminSession);
      await page.goto(`${BASE_URL}/admin/faculty`, { waitUntil: 'networkidle' });

      // Click the first View button in the table
      const viewButton = page.locator('button:has-text("View")').first();
      await viewButton.waitFor({ state: 'visible', timeout: 5000 });
      await viewButton.click();

      // Wait for drawer SheetContent to open
      const sheetContent = page.locator('[data-slot="sheet-content"]');
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });

      // Check close buttons count: exactly ONE
      const closeButtons = sheetContent.locator('button[aria-label="Close"]');
      const closeCount = await closeButtons.count();
      console.log(`Found ${closeCount} close button(s) in Admin Faculty View drawer`);

      if (closeCount !== 1) {
        testErrors.push(`Admin Faculty drawer has ${closeCount} close buttons (expected exactly 1)`);
      } else {
        console.log('✓ Exactly 1 close button confirmed in Admin Faculty drawer');
      }

      // Close via X button
      await closeButtons.first().click();
      await sheetContent.waitFor({ state: 'hidden', timeout: 3000 });
      console.log('✓ Drawer closed cleanly via X button click');

      // Test open via URL (?view=1)
      await page.goto(`${BASE_URL}/admin/faculty?view=1`, { waitUntil: 'networkidle' });
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });
      const urlCloseCount = await sheetContent.locator('button[aria-label="Close"]').count();
      if (urlCloseCount !== 1) {
        testErrors.push(`Admin Faculty drawer opened via URL has ${urlCloseCount} close buttons (expected 1)`);
      } else {
        console.log('✓ Admin Faculty drawer opened via URL has exactly 1 close button');
      }

      await context.close();
    }

    // =========================================================================
    // TEST 4: RESPONSIVE VIEWPORT & NO HORIZONTAL OVERFLOW CHECK
    // (320, 375, 768, 1024, 1280, 1440, 1920 px)
    // =========================================================================
    console.log('\n[TEST 4] Verifying View Drawer Responsiveness & Zero Horizontal Overflow...');
    const viewports = [320, 375, 768, 1024, 1280, 1440, 1920];
    for (const width of viewports) {
      const context = await browser.newContext({ viewport: { width, height: 800 } });
      const page = await context.newPage();

      await setupApiMocks(page, mockAdminSession);
      await page.goto(`${BASE_URL}/admin/students?view=1`, { waitUntil: 'networkidle' });

      const sheetContent = page.locator('[data-slot="sheet-content"]');
      await sheetContent.waitFor({ state: 'visible', timeout: 5000 });

      // Check document overflow
      const overflow = await page.evaluate(() => {
        const docEl = document.documentElement;
        return {
          scrollWidth: docEl.scrollWidth,
          clientWidth: docEl.clientWidth,
          hasOverflow: docEl.scrollWidth > docEl.clientWidth
        };
      });

      if (overflow.hasOverflow) {
        testErrors.push(`Horizontal overflow detected at ${width}px: scrollWidth=${overflow.scrollWidth}, clientWidth=${overflow.clientWidth}`);
      } else {
        console.log(`✓ Width ${width}px: Zero horizontal overflow (scrollWidth=${overflow.scrollWidth}, clientWidth=${overflow.clientWidth})`);
      }

      await context.close();
    }

    // =========================================================================
    // TEST 5: ROUTE SMOKE TEST FOR ALL ROLES
    // =========================================================================
    console.log('\n[TEST 5] Running Whole App Route Smoke Test...');
    const routesToTest = [
      { role: mockStudentSession, path: '/student/dashboard' },
      { role: mockStudentSession, path: '/student/exams' },
      { role: mockStudentSession, path: '/student/performance' },
      { role: mockStudentSession, path: '/student/settings' },
      { role: mockFacultySession, path: '/faculty/dashboard' },
      { role: mockFacultySession, path: '/faculty/generate' },
      { role: mockFacultySession, path: '/faculty/history' },
      { role: mockFacultySession, path: '/faculty/bank' },
      { role: mockFacultySession, path: '/faculty/settings' },
      { role: mockAdminSession, path: '/admin/dashboard' },
      { role: mockAdminSession, path: '/admin/students' },
      { role: mockAdminSession, path: '/admin/faculty' },
      { role: mockAdminSession, path: '/admin/exams' },
      { role: mockAdminSession, path: '/admin/bank' },
      { role: mockAdminSession, path: '/admin/settings' },
      { role: mockSuperAdminSession, path: '/superadmin/institutions' },
      { role: mockSuperAdminSession, path: '/superadmin/users' },
      { role: mockSuperAdminSession, path: '/superadmin/models' },
      { role: mockSuperAdminSession, path: '/superadmin/analytics' },
    ];

    for (const { role, path: routePath } of routesToTest) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();

      const fatalErrors = [];
      page.on('pageerror', (err) => fatalErrors.push(err.message));

      await setupApiMocks(page, role);
      await page.goto(`${BASE_URL}${routePath}`, { waitUntil: 'networkidle' });

      const bodyText = await page.textContent('body');
      const isErrorScreen = bodyText.includes('Unexpected Application Error') || bodyText.includes('Something went wrong');

      if (fatalErrors.length > 0 || isErrorScreen) {
        testErrors.push(`Route ${routePath} failed! Errors: ${fatalErrors.join(', ')} (ErrorScreen: ${isErrorScreen})`);
      } else {
        console.log(`✓ Route [${role.role}] ${routePath} passed cleanly`);
      }

      await context.close();
    }

  } catch (err) {
    testErrors.push(`Test execution exception: ${err.message}`);
  } finally {
    if (browser) await browser.close();
    previewProcess.kill();
  }

  console.log('\n======================================================');
  if (testErrors.length > 0) {
    console.error(`FAILED: ${testErrors.length} test failure(s):`);
    testErrors.forEach(e => console.error('  - ' + e));
    process.exit(1);
  } else {
    console.log('ALL PLAYWRIGHT TESTS PASSED CLEANLY (0 ERRORS)!');
    process.exit(0);
  }
}

run();
