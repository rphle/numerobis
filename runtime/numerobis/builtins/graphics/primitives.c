/* DISCLAIMER: The graphics primitive algorithms in this file were
 * adapted and optimized with assistance from Claude Opus 4.6. */

#include "primitives.h"
#include "state.h"

#include <SDL2/SDL.h>
#include <gc.h>
#include <math.h>
#include <stdbool.h>

static inline void hline(int x0, int x1, int y) {
  if (x0 > x1) {
    int t = x0;
    x0 = x1;
    x1 = t;
  }
  SDL_RenderDrawLine(_renderer, x0, y, x1, y);
}

static inline void sym4(int cx, int cy, int x, int y) {
  SDL_RenderDrawPoint(_renderer, cx + x, cy + y);
  SDL_RenderDrawPoint(_renderer, cx - x, cy + y);
  SDL_RenderDrawPoint(_renderer, cx + x, cy - y);
  SDL_RenderDrawPoint(_renderer, cx - x, cy - y);
}

#define SWAP(a, b)                                                             \
  do {                                                                         \
    __typeof__(a) _t = (a);                                                    \
    (a) = (b);                                                                 \
    (b) = _t;                                                                  \
  } while (0)

void _prim_circle(int cx, int cy, int r, bool filled) {
  if (r <= 0) {
    if (filled)
      SDL_RenderDrawPoint(_renderer, cx, cy);
    return;
  }

  int x = r, y = 0, err = 1 - r;
  while (x >= y) {
    if (filled) {
      hline(cx - x, cx + x, cy + y);
      hline(cx - x, cx + x, cy - y);
      hline(cx - y, cx + y, cy + x);
      hline(cx - y, cx + y, cy - x);
    } else {
      sym4(cx, cy, x, y);
      sym4(cx, cy, y, x);
    }
    y++;
    err += (err < 0) ? 2 * y + 1 : (x--, 2 * (y - x) + 1);
  }
}

void _prim_ellipse(int cx, int cy, int rx, int ry, bool filled) {
  if (rx <= 0 || ry <= 0)
    return;
  if (rx == ry) {
    _prim_circle(cx, cy, rx, filled);
    return;
  }

  long rx2 = (long)rx * rx, ry2 = (long)ry * ry;
  int x = 0, y = ry;
  long dx = 0, dy = 2LL * rx2 * y, p = ry2 - rx2 * ry + rx2 / 4;

  /* Region 1 */
  while (dx < dy) {
    if (filled) {
      hline(cx - x, cx + x, cy + y);
      hline(cx - x, cx + x, cy - y);
    } else
      sym4(cx, cy, x, y);
    x++;
    dx += 2LL * ry2;
    if (p < 0)
      p += ry2 + dx;
    else {
      y--;
      dy -= 2LL * rx2;
      p += ry2 + dx - dy;
    }
  }

  /* Region 2 */
  p = ry2 * ((long)x * x + x) + rx2 * ((long)(y - 1) * (y - 1)) -
      (long)rx2 * ry2;
  while (y >= 0) {
    if (filled) {
      hline(cx - x, cx + x, cy + y);
      hline(cx - x, cx + x, cy - y);
    } else
      sym4(cx, cy, x, y);
    y--;
    dy -= 2LL * rx2;
    if (p > 0)
      p += rx2 - dy;
    else {
      x++;
      dx += 2LL * ry2;
      p += rx2 - dy + dx;
    }
  }
}

void _prim_arc(int cx, int cy, int r, float deg0, float deg1, bool filled) {
  if (r <= 0)
    return;
  if (deg1 < deg0)
    SWAP(deg0, deg1);

  float rad0 = deg0 * (float)M_PI / 180.f;
  float rad1 = deg1 * (float)M_PI / 180.f;
  int segs = (int)fmaxf(16.f, (deg1 - deg0) / 2.f);
  float step = (rad1 - rad0) / segs;

  if (!filled) {
    for (int s = 0; s < segs; s++) {
      float a0 = rad0 + step * s, a1 = a0 + step;
      SDL_RenderDrawLine(_renderer, cx + (int)(r * cosf(a0)),
                         cy + (int)(r * sinf(a0)), cx + (int)(r * cosf(a1)),
                         cy + (int)(r * sinf(a1)));
    }
    return;
  }

  /* Filled sector: per-pixel angular test */
  int r2 = r * r;
  float sweep = deg1 - deg0;
  float ex0 = cosf(rad0), ey0 = sinf(rad0);
  float ex1 = cosf(rad1), ey1 = sinf(rad1);

  for (int dy = -r; dy <= r; dy++) {
    int rowY = cy + dy;
    float fdy = (float)dy;
    float half = sqrtf(fmaxf(0.f, (float)r2 - fdy * fdy));
    int xl = (int)ceilf(-half), xr = (int)floorf(half);

    if (sweep >= 360.f) {
      hline(cx + xl, cx + xr, rowY);
      continue;
    }

    int span_l = cx + xr + 1, span_r = cx + xl - 1;
    for (int dx = xl; dx <= xr; dx++) {
      float fdx = (float)dx;
      float cross0 = ex0 * fdy - ey0 * fdx;
      float cross1 = ex1 * fdy - ey1 * fdx;
      bool inside = (sweep <= 180.f) ? (cross0 >= 0.f && cross1 <= 0.f)
                                     : (cross0 >= 0.f || cross1 <= 0.f);
      if (inside && dx * dx + dy * dy <= r2) {
        if (cx + dx < span_l)
          span_l = cx + dx;
        if (cx + dx > span_r)
          span_r = cx + dx;
      }
    }
    if (span_l <= span_r) {
      if (cx < span_l)
        span_l = cx;
      if (cx > span_r)
        span_r = cx;
      hline(span_l, span_r, rowY);
    }
  }
}

void _prim_rounded_rect(int x, int y, int w, int h, int r, bool filled) {
  if (r > w / 2)
    r = w / 2;
  if (r > h / 2)
    r = h / 2;

  if (!filled) {
    SDL_RenderDrawLine(_renderer, x + r, y, x + w - r, y);
    SDL_RenderDrawLine(_renderer, x + r, y + h, x + w - r, y + h);
    SDL_RenderDrawLine(_renderer, x, y + r, x, y + h - r);
    SDL_RenderDrawLine(_renderer, x + w, y + r, x + w, y + h - r);
    _prim_arc(x + r, y + r, r, 180.f, 270.f, false);
    _prim_arc(x + w - r, y + r, r, 270.f, 360.f, false);
    _prim_arc(x + w - r, y + h - r, r, 0.f, 90.f, false);
    _prim_arc(x + r, y + h - r, r, 90.f, 180.f, false);
    return;
  }

  SDL_Rect rects[3] = {
      {x + r, y, w - 2 * r, h},
      {x, y + r, r, h - 2 * r},
      {x + w - r, y + r, r, h - 2 * r},
  };
  SDL_RenderFillRects(_renderer, rects, 3);

  /* Corner centres */
  const int ccx[] = {x + r, x + w - r, x + r, x + w - r};
  const int ccy[] = {y + r, y + r, y + h - r, y + h - r};
  const int sx[] = {-1, 1, -1, 1};
  const int sy[] = {-1, -1, 1, 1};

  int px = r, py = 0, err = 1 - r;
  while (px >= py) {
    for (int c = 0; c < 4; c++) {
      hline(ccx[c], ccx[c] + sx[c] * px, ccy[c] + sy[c] * py);
      hline(ccx[c], ccx[c] + sx[c] * py, ccy[c] + sy[c] * px);
    }
    py++;
    err += (err < 0) ? 2 * py + 1 : (px--, 2 * (py - px) + 1);
  }
}

void _prim_thick_line(int x1, int y1, int x2, int y2, double t) {
  if (t <= 1.0) {
    SDL_RenderDrawLine(_renderer, x1, y1, x2, y2);
    return;
  }

  double dx = x2 - x1, dy = y2 - y1, len = sqrt(dx * dx + dy * dy);
  if (len < 0.5) {
    _prim_circle(x1, y1, (int)(t / 2.0), true);
    return;
  }

  double nx = -dy / len * (t / 2.0), ny = dx / len * (t / 2.0);
  SDL_Point pts[4] = {
      {(int)(x1 + nx + .5), (int)(y1 + ny + .5)},
      {(int)(x2 + nx + .5), (int)(y2 + ny + .5)},
      {(int)(x2 - nx + .5), (int)(y2 - ny + .5)},
      {(int)(x1 - nx + .5), (int)(y1 - ny + .5)},
  };
  _prim_polygon(pts, 4, true);
}

void _prim_polygon(SDL_Point *pts, int n, bool filled) {
  if (n < 2)
    return;

  for (int i = 0; i < n; i++)
    SDL_RenderDrawLine(_renderer, pts[i].x, pts[i].y, pts[(i + 1) % n].x,
                       pts[(i + 1) % n].y);
  if (!filled || n < 3)
    return;

  int ymin = pts[0].y, ymax = pts[0].y;
  for (int i = 1; i < n; i++) {
    if (pts[i].y < ymin)
      ymin = pts[i].y;
    if (pts[i].y > ymax)
      ymax = pts[i].y;
  }
  if (ymin == ymax)
    return;

  int *xs = GC_MALLOC_ATOMIC(n * sizeof(int));
  if (!xs)
    return;

  for (int scanY = ymin; scanY <= ymax; scanY++) {
    int cnt = 0;
    for (int i = 0, j = n - 1; i < n; j = i++) {
      int yi = pts[i].y, yj = pts[j].y;
      if ((yi <= scanY && yj > scanY) || (yj <= scanY && yi > scanY))
        xs[cnt++] =
            pts[i].x +
            (int)(((long)(scanY - yi) * (pts[j].x - pts[i].x)) / (yj - yi));
    }
    /* Insertion sort */
    for (int a = 1; a < cnt; a++) {
      int v = xs[a], b = a;
      while (b > 0 && xs[b - 1] > v) {
        xs[b] = xs[b - 1];
        b--;
      }
      xs[b] = v;
    }
    for (int a = 0; a + 1 < cnt; a += 2)
      hline(xs[a], xs[a + 1], scanY);
  }
}
