import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const adminSession = {
  access: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mockToken",
  refresh: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mockToken",
  role: "admin",
  user: { id: 5, first_name: "HARSH", last_name: "POSHIYA", email: "poshiya.2102@gmail.com", institution: { id: 2, name: "GLS University" } }
};

// Generate realistic mock data with extremely long names, emails, and departments
const mockFacultyRows = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  full_name: i % 2 === 0
    ? `Dr. Alexander Montgomery-Smith The ${i + 1}th of Academic Excellence & Computational Architecture`
    : `Prof. Jacqueline Bernadette Van Der Beek #${i + 1} Distinguished Dean`,
  email: `alexander.montgomerysmith.senior.fellow.${i + 1}@computer-science-and-genetic-engineering.glsuniversity.edu`,
  employee_id: `FAC-2026-${String(i + 1).padStart(3, '0')}`,
  department: i % 3 === 0
    ? "Computer Science, Artificial Intelligence, Robotics & Machine Learning"
    : i % 3 === 1
      ? "Biotechnology & Computational Genetic Systems Engineering"
      : "Information Technology & Distributed Autonomous Cloud Systems",
  designation: i % 2 === 0 ? "Distinguished Senior Professor & Dean" : "Associate Department Head",
  is_active: i % 4 !== 0,
  status: i % 4 !== 0 ? "Active" : "Inactive",
}));

const mockStudentRows = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  full_name: `Student Alexander Maximilian Montgomery-Smith #${i + 1}`,
  email: `student.alexander.maximilian.${i + 1}@engineering.glsuniversity.edu`,
  roll_number: `STU-2026-${String(i + 1).padStart(4, '0')}`,
  department: "Computer Science, Artificial Intelligence & Machine Learning",
  exams_attempted: 5,
  average_score: 78.5,
  highest_score: 95,
  lowest_score: 62,
  performance_status: "good",
}));

const mockExamRows = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  title: `Advanced Cloud Computing & Distributed Quantum Cryptography Architecture #${i + 1}`,
  subject: "Cloud & Network Security",
  faculty_name: "Dr. Alexander Montgomery-Smith",
  department_name: "Computer Science and Engineering",
  duration_minutes: 90,
  total_marks: 100,
  questions_count: 35,
  attempts_count: 120,
  status: "published",
  created_at: "2026-10-15T10:00:00Z",
}));

const screenshotDir = path.resolve('tests/screenshots');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

const widths = [320, 375, 768, 1024, 1280, 1366, 1440, 1500, 1920];
const zooms = [1.0, 1.1, 1.25, 2.0];
const pageSizes = [10, 25, 50, 100];

async function run() {
  const browser = await chromium.launch({ headless: true });
  let totalTests = 0;
  let failures = 0;
  const failureReports = [];
  const sampleReports = [];

  try {
    // 1. Audit Admin Faculty across all specified widths, zooms, sidebar states
    console.log("=== STARTING ADMIN FACULTY LAYOUT AUDIT ===");
    for (const w of widths) {
      for (const sidebarOpen of [true, false]) {
        for (const zoom of zooms) {
          totalTests++;
          const ctx = await browser.newContext({
            viewport: { width: w, height: 900 },
            deviceScaleFactor: zoom,
          });
          const page = await ctx.newPage();

          // Intercept Auth
          await page.route('**/api/auth/me**', (route) => {
            route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({ status: 'success', role: 'admin', user: adminSession.user }),
            });
          });

          // Intercept Faculty API
          await page.route('**/api/admin/faculty**', (route) => {
            const url = new URL(route.request().url());
            const p = parseInt(url.searchParams.get('page') || '1', 10);
            const ps = parseInt(url.searchParams.get('page_size') || '10', 10);
            const offset = (p - 1) * ps;
            const paged = mockFacultyRows.slice(offset, offset + ps);
            const totalPages = Math.ceil(mockFacultyRows.length / ps);

            route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                status: 'success',
                data: paged,
                results: paged,
                count: mockFacultyRows.length,
                total_count: mockFacultyRows.length,
                total_pages: totalPages,
                page: p,
                page_size: ps,
                has_next: p < totalPages,
                has_prev: p > 1,
                pagination: {
                  page: p,
                  page_size: ps,
                  total_count: mockFacultyRows.length,
                  total_pages: totalPages,
                  has_next: p < totalPages,
                  has_prev: p > 1,
                },
              }),
            });
          });

          await page.route('**/api/departments**', (route) => {
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: [] }) });
          });

          await page.route('**/api/notifications/**', (route) => {
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ notifications: [], unread_count: 0 }) });
          });

          await page.addInitScript(({ session, sbOpen }) => {
            window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
            window.localStorage.setItem("examai-admin-sidebar-open", sbOpen ? "true" : "false");
          }, { session: adminSession, sbOpen: sidebarOpen });

          await page.goto("http://127.0.0.1:3000/admin/faculty", { waitUntil: "networkidle" });
          await page.waitForTimeout(400);

          const result = await page.evaluate(() => {
            const docEl = document.documentElement;
            const body = document.body;
            const hasDocOverflow = docEl.scrollWidth > docEl.clientWidth;
            const hasBodyOverflow = body.scrollWidth > body.clientWidth;

            // Check desktop table wrapper if >= 768px
            const table = document.querySelector('table');
            let hasWrapperOverflow = false;
            let wrapperScrollWidth = 0;
            let wrapperClientWidth = 0;
            let actionsClipped = false;
            let maxButtonRight = 0;
            let wrapperRight = 0;

            if (table && table.offsetWidth > 0) {
              const wrapper = table.parentElement;
              wrapperScrollWidth = wrapper.scrollWidth;
              wrapperClientWidth = wrapper.clientWidth;
              hasWrapperOverflow = wrapperScrollWidth > wrapperClientWidth;

              const wrapperRect = wrapper.getBoundingClientRect();
              wrapperRight = wrapperRect.right;
              const actionCells = Array.from(table.querySelectorAll('tbody tr td:last-child'));
              for (const cell of actionCells) {
                const buttons = Array.from(cell.querySelectorAll('button, a'));
                for (const b of buttons) {
                  const bRect = b.getBoundingClientRect();
                  if (bRect.right > maxButtonRight) maxButtonRight = bRect.right;
                  // Allow up to 1px rounding tolerance
                  if (bRect.right > wrapperRect.right + 1) {
                    actionsClipped = true;
                  }
                }
              }
            }

            return {
              docScrollWidth: docEl.scrollWidth,
              docClientWidth: docEl.clientWidth,
              hasDocOverflow,
              hasBodyOverflow,
              hasWrapperOverflow,
              wrapperScrollWidth,
              wrapperClientWidth,
              actionsClipped,
              maxButtonRight,
              wrapperRight,
            };
          });

          const failed = result.hasDocOverflow || result.hasBodyOverflow || result.hasWrapperOverflow || result.actionsClipped;
          if (failed) {
            failures++;
            failureReports.push({
              page: 'AdminFaculty',
              viewport: w,
              sidebar: sidebarOpen ? 'Open' : 'Closed',
              zoom: `${Math.round(zoom * 100)}%`,
              result,
            });
          }

          if (zoom === 1.0 && sidebarOpen && [375, 768, 1500].includes(w)) {
            const shotPath = path.join(screenshotDir, `v2_admin_faculty_${w}px.png`);
            await page.screenshot({ path: shotPath, fullPage: false });
          }

          if (zoom === 1.0) {
            sampleReports.push({
              viewport: w,
              sidebar: sidebarOpen ? 'Open' : 'Closed',
              docScroll: result.docScrollWidth,
              docClient: result.docClientWidth,
              wrapScroll: result.wrapperScrollWidth,
              wrapClient: result.wrapperClientWidth,
              clipped: result.actionsClipped,
            });
          }

          await ctx.close();
        }
      }
    }

    // 2. Test pagination rows per page: 10, 25, 50, 100
    console.log("=== TESTING ROWS PER PAGE INTERACTION (10, 25, 50, 100) ===");
    for (const ps of pageSizes) {
      totalTests++;
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const p = await ctx.newPage();

      await p.route('**/api/auth/me**', (route) => {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', role: 'admin', user: adminSession.user }) });
      });

      await p.route('**/api/admin/faculty**', (route) => {
        const url = new URL(route.request().url());
        const pageNum = parseInt(url.searchParams.get('page') || '1', 10);
        const pageSize = parseInt(url.searchParams.get('page_size') || String(ps), 10);
        const offset = (pageNum - 1) * pageSize;
        const paged = mockFacultyRows.slice(offset, offset + pageSize);
        const totalPages = Math.ceil(mockFacultyRows.length / pageSize);

        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            status: 'success',
            data: paged,
            count: mockFacultyRows.length,
            total_count: mockFacultyRows.length,
            total_pages: totalPages,
            page: pageNum,
            page_size: pageSize,
            pagination: { page: pageNum, page_size: pageSize, total_count: mockFacultyRows.length, total_pages: totalPages },
          }),
        });
      });

      await p.route('**/api/departments**', (route) => {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: [] }) });
      });
      await p.route('**/api/notifications/**', (route) => {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ notifications: [], unread_count: 0 }) });
      });

      await p.addInitScript(({ session }) => {
        window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
      }, { session: adminSession });

      await p.goto(`http://127.0.0.1:3000/admin/faculty?page=1&page_size=${ps}`, { waitUntil: "networkidle" });
      await p.waitForTimeout(400);

      const navText = await p.textContent('nav[aria-label="Pagination"]');
      const expectedText = `Showing 1 to ${ps} of 100`;
      if (!navText || !navText.includes(expectedText)) {
        console.error(`Page size test failed for ${ps}: Expected '${expectedText}', got '${navText}'`);
        failures++;
      }

      const overflow = await p.evaluate(() => {
        const docEl = document.documentElement;
        const table = document.querySelector('table');
        const wrap = table ? table.parentElement : null;
        return {
          docOverflow: docEl.scrollWidth > docEl.clientWidth,
          wrapOverflow: wrap ? wrap.scrollWidth > wrap.clientWidth : false,
        };
      });

      if (overflow.docOverflow || overflow.wrapOverflow) {
        failures++;
        console.error(`Overflow detected during page size ${ps} test:`, overflow);
      }

      await ctx.close();
    }

    // 3. Audit Other Admin Tables: Admin Students & Admin Exams
    console.log("=== AUDITING OTHER ADMIN TABLES (Admin Students & Admin Exams) ===");
    for (const pathUrl of ['/admin/students', '/admin/exams']) {
      for (const w of [375, 768, 1280, 1500]) {
        totalTests++;
        const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        const p = await ctx.newPage();

        await p.route('**/api/auth/me**', (route) => {
          route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', role: 'admin', user: adminSession.user }) });
        });

        await p.route('**/api/admin/students**', (route) => {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              status: 'success',
              data: mockStudentRows.slice(0, 10),
              count: 100,
              total_count: 100,
              total_pages: 10,
              statistics: { total_students: 100, active_students: 95, overall_average_score: 78.5, students_below_pass: 4 },
            }),
          });
        });

        await p.route('**/api/admin/exams**', (route) => {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              status: 'success',
              data: mockExamRows.slice(0, 10),
              count: 50,
              total_count: 50,
              total_pages: 5,
              statistics: { total_exams: 50, published_exams: 42, active_exams: 5, draft_exams: 3 },
            }),
          });
        });

        await p.route('**/api/departments**', (route) => {
          route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: [] }) });
        });
        await p.route('**/api/notifications/**', (route) => {
          route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ notifications: [], unread_count: 0 }) });
        });

        await p.addInitScript(({ session }) => {
          window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
        }, { session: adminSession });

        await p.goto(`http://127.0.0.1:3000${pathUrl}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(400);

        const check = await p.evaluate(() => {
          const docEl = document.documentElement;
          const body = document.body;
          const table = document.querySelector('table');
          const wrap = table ? table.parentElement : null;
          return {
            hasDocOverflow: docEl.scrollWidth > docEl.clientWidth,
            hasBodyOverflow: body.scrollWidth > body.clientWidth,
            hasWrapOverflow: wrap ? wrap.scrollWidth > wrap.clientWidth : false,
          };
        });

        if (check.hasDocOverflow || check.hasBodyOverflow || check.hasWrapOverflow) {
          failures++;
          failureReports.push({ page: pathUrl, viewport: w, result: check });
        }

        await ctx.close();
      }
    }

    console.log("\n=== COMPREHENSIVE SAMPLE AUDIT REPORT (Zoom: 100%) ===");
    console.table(sampleReports);

    console.log(`\nTOTAL CONFIGURATIONS TESTED: ${totalTests}`);
    console.log(`FAILURES: ${failures}`);

    if (failures > 0) {
      console.error("FAILURES DETECTED:", JSON.stringify(failureReports, null, 2));
      process.exit(1);
    } else {
      console.log("SUCCESS: ALL tests passed with ZERO horizontal scrollbars and ZERO clipped action buttons!");
      process.exit(0);
    }
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
