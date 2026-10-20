import { chromium } from 'playwright';

const adminSession = {
  access: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mockToken",
  refresh: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mockToken",
  role: "admin",
  user: { id: 5, first_name: "HARSH", last_name: "POSHIYA", email: "poshiya.2102@gmail.com", institution: { id: 2, name: "GLS University" } }
};

const mockFacultyRows = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1,
  full_name: i % 2 === 0
    ? `Dr. Alexander Montgomery-Smith The ${i + 1}th`
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

async function run() {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const w of [1500, 1440, 1280, 1024, 768]) {
      for (const sidebarOpen of [true, false]) {
        const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        const page = await ctx.newPage();

        await page.route('**/api/auth/me**', (route) => {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              status: 'success',
              role: 'admin',
              user: adminSession.user,
            }),
          });
        });

        await page.route('**/api/admin/faculty**', (route) => {
          route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              status: 'success',
              data: mockFacultyRows,
              results: mockFacultyRows,
              count: 25,
              total_count: 25,
              total_pages: 3,
              page: 1,
              page_size: 10,
              has_next: true,
              has_prev: false,
              pagination: {
                page: 1,
                page_size: 10,
                total_count: 25,
                total_pages: 3,
                has_next: true,
                has_prev: false,
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
        await page.waitForTimeout(600);

        const diagnostic = await page.evaluate(() => {
          const table = document.querySelector('table');
          if (!table) return { error: "No table found" };
          const wrapper = table.parentElement;

          const tableComputed = window.getComputedStyle(table);
          const wrapperComputed = window.getComputedStyle(wrapper);

          // Columns
          const ths = Array.from(table.querySelectorAll('thead th'));
          const cols = Array.from(table.querySelectorAll('colgroup col'));
          const colData = ths.map((th, idx) => {
            const col = cols[idx];
            const thRect = th.getBoundingClientRect();
            return {
              index: idx,
              name: th.innerText.trim(),
              thWidth: thRect.width,
              colClass: col ? col.className : '',
            };
          });
          const sumCols = colData.reduce((acc, c) => acc + c.thWidth, 0);

          // Ancestor inspection
          const ancestors = [];
          let curr = wrapper;
          while (curr && curr !== document.documentElement) {
            const cs = window.getComputedStyle(curr);
            const parent = curr.parentElement;
            const parentCs = parent ? window.getComputedStyle(parent) : null;
            const isFlexOrGridChild = parentCs ? (parentCs.display.includes('flex') || parentCs.display.includes('grid')) : false;

            ancestors.push({
              tag: curr.tagName.toLowerCase(),
              className: curr.className,
              display: cs.display,
              width: cs.width,
              minWidth: cs.minWidth,
              maxWidth: cs.maxWidth,
              overflow: cs.overflow,
              overflowX: cs.overflowX,
              clientWidth: curr.clientWidth,
              scrollWidth: curr.scrollWidth,
              isFlexOrGridChild,
              hasMinW0: cs.minWidth === '0px',
            });
            curr = curr.parentElement;
          }

          // Sidebar
          const aside = document.querySelector('aside');
          const sidebarData = aside ? {
            width: aside.getBoundingClientRect().width,
            computedWidth: window.getComputedStyle(aside).width,
            className: aside.className,
          } : null;

          // Main area
          const main = document.querySelector('main');
          const mainParent = main ? main.parentElement : null;
          const mainData = {
            mainClientWidth: main ? main.clientWidth : null,
            mainScrollWidth: main ? main.scrollWidth : null,
            mainParentClientWidth: mainParent ? mainParent.clientWidth : null,
            mainParentScrollWidth: mainParent ? mainParent.scrollWidth : null,
            mainParentClass: mainParent ? mainParent.className : '',
          };

          // Action column and clipping check
          const firstRow = table.querySelector('tbody tr');
          const actionsCell = firstRow ? firstRow.querySelector('td:last-child') : null;
          const wrapperRect = wrapper.getBoundingClientRect();
          let actionsClipping = null;
          if (actionsCell) {
            const cellRect = actionsCell.getBoundingClientRect();
            const actionButtons = Array.from(actionsCell.querySelectorAll('button, a'));
            const buttonsRight = actionButtons.map(b => b.getBoundingClientRect().right);
            const maxRight = buttonsRight.length ? Math.max(...buttonsRight) : cellRect.right;
            actionsClipping = {
              cellRight: cellRect.right,
              maxButtonRight: maxRight,
              wrapperRight: wrapperRect.right,
              isClipped: maxRight > wrapperRect.right,
              pixelsClipped: Math.max(0, maxRight - wrapperRect.right),
            };
          }

          // Now check for white-space nowrap, min-width, fixed width, emails
          const cellIssues = [];
          if (firstRow) {
            Array.from(firstRow.children).forEach((td, idx) => {
              const cs = window.getComputedStyle(td);
              cellIssues.push({
                colIndex: idx,
                colName: ths[idx] ? ths[idx].innerText.trim() : `col_${idx}`,
                whiteSpace: cs.whiteSpace,
                width: cs.width,
                minWidth: cs.minWidth,
                text: td.innerText.replace(/\n/g, ' | ').slice(0, 50),
              });
            });
          }

          return {
            wrapper: {
              clientWidth: wrapper.clientWidth,
              scrollWidth: wrapper.scrollWidth,
              hasScrollbar: wrapper.scrollWidth > wrapper.clientWidth,
              overflowX: wrapperComputed.overflowX,
              className: wrapper.className,
            },
            table: {
              offsetWidth: table.offsetWidth,
              scrollWidth: table.scrollWidth,
              computedWidth: tableComputed.width,
              computedMinWidth: tableComputed.minWidth,
              computedTableLayout: tableComputed.tableLayout,
            },
            colData,
            sumCols,
            actionsClipping,
            cellIssues,
            sidebarData,
            mainData,
            ancestors,
          };
        });

        console.log(`\n=================== VIEWPORT ${w}px (Sidebar: ${sidebarOpen ? 'Open' : 'Closed'}) ===================`);
        console.log(`Wrapper clientWidth: ${diagnostic.wrapper.clientWidth}px | scrollWidth: ${diagnostic.wrapper.scrollWidth}px | Has Wrapper Scrollbar: ${diagnostic.wrapper.hasScrollbar}`);
        console.log(`Table offsetWidth: ${diagnostic.table.offsetWidth}px | scrollWidth: ${diagnostic.table.scrollWidth}px | width: ${diagnostic.table.computedWidth} | min-width: ${diagnostic.table.computedMinWidth} | layout: ${diagnostic.table.computedTableLayout}`);
        console.log(`Sum of column widths: ${diagnostic.sumCols.toFixed(2)}px vs Wrapper clientWidth: ${diagnostic.wrapper.clientWidth}px (Diff: ${(diagnostic.sumCols - diagnostic.wrapper.clientWidth).toFixed(2)}px)`);
        console.log("Columns:", diagnostic.colData);
        console.log("Actions clipping:", diagnostic.actionsClipping);
        console.log("Cell styles:", diagnostic.cellIssues);
        console.log("Sidebar:", diagnostic.sidebarData);
        console.log("Main:", diagnostic.mainData);
        console.log("Ancestors:", diagnostic.ancestors.slice(0, 5));

        await ctx.close();
      }
    }
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
