import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const adminSession = {
  access: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkyMzQ5OTA3LCJpYXQiOjE3OTIzNDgxMDcsImp0aSI6ImNjYTM4ZDAwMmEyMDQ4OGU5ZWIyZjU2NWFlZGEwY2Q3IiwidXNlcl9pZCI6IjUiLCJyb2xlIjoiYWRtaW4iLCJpbnN0aXR1dGlvbl9pZCI6Mn0.qm3GXAWp56daf0g7mjUWwoHWPDbvW2Q7q93hKEyI3jU",
  refresh: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc5Mjk1MjkwNywiaWF0IjoxNzkyMzQ4MTA3LCJqdGkiOiIyNmIxMDM0NTI3YTc0MGExYmNhYTg2NDJlODFiNjI3NCIsInVzZXJfaWQiOiI1Iiwicm9sZSI6ImFkbWluIiwiaW5zdGl0dXRpb25faWQiOjJ9.mM-MYlc_vdA6lXS_ub5WlHZzfqNTwxO8PLhkleo-hN0",
  role: "admin",
  user: { id: 5, first_name: "HARSH", last_name: "POSHIYA", email: "poshiya.2102@gmail.com", institution: { id: 2, name: "GLS University" } }
};

// Generate 25 realistic mock faculty with very long names, departments, and emails
const mockFacultyRows = Array.from({ length: 25 }, (_, i) => ({
  id: i + 1,
  full_name: i % 2 === 0
    ? `Dr. Alexander Montgomery-Smith The ${i + 1}th of Academic Excellence`
    : `Prof. Jacqueline Bernadette Van Der Beek #${i + 1}`,
  email: `alexander.montgomerysmith.senior.fellow.${i + 1}@computer-science-and-engineering.glsuniversity.edu`,
  employee_id: `FAC-2026-${String(i + 1).padStart(3, '0')}`,
  department: i % 3 === 0
    ? "Computer Science, Artificial Intelligence & Machine Learning"
    : i % 3 === 1
      ? "Biotechnology & Computational Genetic Engineering"
      : "Information Technology & Distributed Cloud Systems",
  designation: i % 2 === 0 ? "Distinguished Senior Professor & Dean" : "Associate Department Head",
  is_active: i % 4 !== 0,
  status: i % 4 !== 0 ? "Active" : "Inactive",
}));

const viewports = [320, 375, 768, 1024, 1280, 1440, 1920];
const screenshotDir = path.resolve('tests/screenshots');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  let failures = 0;
  const reports = [];

  try {
    for (const w of viewports) {
      for (const sidebarOpen of [true, false]) {
        for (const zoom of [1, 2]) {
          const ctx = await browser.newContext({
            viewport: { width: w, height: 900 },
            deviceScaleFactor: zoom,
          });
          const page = await ctx.newPage();

          // Mock paginated API response
          await page.route('**/api/admin/faculty**', (route) => {
            if (route.request().method() === 'GET') {
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
                  message: 'Faculty fetched successfully.',
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
                  total_faculty: mockFacultyRows.length,
                  active_faculty: 19,
                  inactive_faculty: 6,
                  total_departments: 3,
                  statistics: {
                    total_faculty: mockFacultyRows.length,
                    active_faculty: 19,
                    inactive_faculty: 6,
                    total_departments: 3,
                  },
                }),
              });
            } else {
              route.continue();
            }
          });

          await page.route('**/api/departments**', (route) => {
            route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                status: 'success',
                data: [
                  { id: 1, department_name: "Computer Science, Artificial Intelligence & Machine Learning", code: "CSAI" },
                  { id: 2, department_name: "Biotechnology & Computational Genetic Engineering", code: "BTGE" },
                  { id: 3, department_name: "Information Technology & Distributed Cloud Systems", code: "ITDC" },
                ],
              }),
            });
          });

          await page.route('**/api/auth/me**', (route) => {
            route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                status: 'success',
                message: 'User authenticated',
                role: 'admin',
                user: {
                  id: 5,
                  first_name: 'HARSH',
                  last_name: 'POSHIYA',
                  email: 'poshiya.2102@gmail.com',
                  institution: {
                    id: 2,
                    institution_name: 'GLS University',
                    institution_code: 'GLSU',
                  },
                },
              }),
            });
          });

          await page.route('**/api/notifications/**', (route) => {
            route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({ notifications: [], unread_count: 0 }),
            });
          });

          await page.addInitScript(({ session, sbOpen }) => {
            window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
            window.localStorage.setItem("examai-admin-sidebar-open", sbOpen ? "true" : "false");
          }, { session: adminSession, sbOpen: sidebarOpen });

          await page.goto("http://127.0.0.1:3000/admin/faculty", { waitUntil: "networkidle" });
          await page.waitForTimeout(400);

          const overflowCheck = await page.evaluate(() => {
            const docEl = document.documentElement;
            const body = document.body;
            return {
              scrollWidth: docEl.scrollWidth,
              clientWidth: docEl.clientWidth,
              hasDocOverflow: docEl.scrollWidth > docEl.clientWidth,
              hasBodyOverflow: body.scrollWidth > body.clientWidth,
            };
          });

          const hasOverflow = overflowCheck.hasDocOverflow || overflowCheck.hasBodyOverflow;
          if (hasOverflow) {
            failures++;
          }

          reports.push({
            viewport: w,
            sidebar: sidebarOpen ? 'Expanded' : 'Collapsed',
            zoom: `${zoom * 100}%`,
            scrollWidth: overflowCheck.scrollWidth,
            clientWidth: overflowCheck.clientWidth,
            hasOverflow,
          });

          // Take screenshots at 3 widths (375, 768, 1280) when sidebar is Expanded at 100% zoom
          if (zoom === 1 && sidebarOpen && [375, 768, 1280].includes(w)) {
            const shotPath = path.join(screenshotDir, `admin_faculty_${w}px.png`);
            await page.screenshot({ path: shotPath, fullPage: false });
          }

          await ctx.close();
        }
      }
    }

    // Now test pagination interactive flow on 1280px
    const testCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const testPage = testCtx.newPage();
    const p = await testPage;

    await p.route('**/api/admin/faculty**', (route) => {
      const url = new URL(route.request().url());
      const pageNum = parseInt(url.searchParams.get('page') || '1', 10);
      const pageSize = parseInt(url.searchParams.get('page_size') || '10', 10);
      const offset = (pageNum - 1) * pageSize;
      const paged = mockFacultyRows.slice(offset, offset + pageSize);
      const totalPages = Math.ceil(mockFacultyRows.length / pageSize);

      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: paged,
          pagination: {
            page: pageNum,
            page_size: pageSize,
            total_count: mockFacultyRows.length,
            total_pages: totalPages,
            has_next: pageNum < totalPages,
            has_prev: pageNum > 1,
          },
          total_faculty: mockFacultyRows.length,
          active_faculty: 19,
          inactive_faculty: 6,
          total_departments: 3,
        }),
      });
    });

    await p.route('**/api/departments**', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: [] }) });
    });

    await p.route('**/api/auth/me**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'User authenticated',
          role: 'admin',
          user: {
            id: 5,
            first_name: 'HARSH',
            last_name: 'POSHIYA',
            email: 'poshiya.2102@gmail.com',
            institution: {
              id: 2,
              institution_name: 'GLS University',
              institution_code: 'GLSU',
            },
          },
        }),
      });
    });

    await p.route('**/api/notifications/**', (route) => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ notifications: [], unread_count: 0 }) });
    });

    await p.addInitScript(({ session }) => {
      window.sessionStorage.setItem("exam_ai_auth", JSON.stringify(session));
    }, { session: adminSession });

    await p.goto("http://127.0.0.1:3000/admin/faculty", { waitUntil: "networkidle" });
    await p.waitForTimeout(500);

    // Verify page 1 shows "Showing 1 to 10 of 25 faculty"
    const textP1 = await p.textContent('nav[aria-label="Pagination"]');
    if (!textP1 || !textP1.includes('Showing 1 to 10 of 25')) {
      console.error("Pagination test failed: Expected 'Showing 1 to 10 of 25' on page 1, got:", textP1);
      failures++;
    }

    // Click Next button
    const nextBtn = p.locator('button[aria-label="Go to next page"]');
    await nextBtn.click();
    await p.waitForTimeout(400);

    const textP2 = await p.textContent('nav[aria-label="Pagination"]');
    if (!textP2 || !textP2.includes('Showing 11 to 20 of 25')) {
      console.error("Pagination test failed: Expected 'Showing 11 to 20 of 25' on page 2, got:", textP2);
      failures++;
    }

    // Change rows per page to 25
    const rowsSelect = p.locator('select#rows-per-page');
    await rowsSelect.selectOption('25');
    await p.waitForTimeout(400);

    const textP3 = await p.textContent('nav[aria-label="Pagination"]');
    if (!textP3 || !textP3.includes('Showing 1 to 25 of 25')) {
      console.error("Pagination test failed: Expected 'Showing 1 to 25 of 25' after page size change, got:", textP3);
      failures++;
    }

    await testCtx.close();

    console.log("=== VIEWPORT OVERFLOW AUDIT REPORT ===");
    console.table(reports);

    if (failures > 0) {
      console.error(`FAILED: ${failures} layout or pagination failures detected.`);
      process.exit(1);
    } else {
      console.log(`SUCCESS: All 28 viewport configurations and interactive pagination tests PASSED with ZERO horizontal overflow.`);
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
