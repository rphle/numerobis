/* DISCLAIMER: The graphics primitive algorithms in this file were
 * adapted and optimized with assistance from Claude Opus 4.6. */

#include "primitives.h"
#include "state.h"

#include <SDL2/SDL.h>
#include <glib.h>
#include <math.h>

static inline void hline(gint32 x0, gint32 x1, gint32 y) {
  if (x0 > x1) {
    gint32 t = x0;
    x0 = x1;
    x1 = t;
  }
  SDL_RenderDrawLine(_renderer, x0, y, x1, y);
}

static inline void sym4(gint32 cx, gint32 cy, gint32 x, gint32 y) {
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

void _prim_circle(gint32 cx, gint32 cy, gint32 r, gboolean filled) {
  if (r <= 0) {
    if (filled)
      SDL_RenderDrawPoint(_renderer, cx, cy);
    return;
  }

  gint32 x = r, y = 0, err = 1 - r;
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

void _prim_ellipse(gint32 cx, gint32 cy, gint32 rx, gint32 ry,
                   gboolean filled) {
  if (rx <= 0 || ry <= 0)
    return;
  if (rx == ry) {
    _prim_circle(cx, cy, rx, filled);
    return;
  }

  gint64 rx2 = (gint64)rx * rx, ry2 = (gint64)ry * ry;
  gint32 x = 0, y = ry;
  gint64 dx = 0, dy = 2LL * rx2 * y, p = ry2 - rx2 * ry + rx2 / 4;

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
  p = ry2 * ((gint64)x * x + x) + rx2 * ((gint64)(y - 1) * (y - 1)) -
      (gint64)rx2 * ry2;
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

void _prim_arc(gint32 cx, gint32 cy, gint32 r, gfloat deg0, gfloat deg1,
               gboolean filled) {
  if (r <= 0)
    return;
  if (deg1 < deg0)
    SWAP(deg0, deg1);

  gfloat rad0 = deg0 * (gfloat)M_PI / 180.f;
  gfloat rad1 = deg1 * (gfloat)M_PI / 180.f;
  int segs = (int)fmaxf(16.f, (deg1 - deg0) / 2.f);
  gfloat step = (rad1 - rad0) / segs;

  if (!filled) {
    for (int s = 0; s < segs; s++) {
      gfloat a0 = rad0 + step * s, a1 = a0 + step;
      SDL_RenderDrawLine(
          _renderer, cx + (gint32)(r * cosf(a0)), cy + (gint32)(r * sinf(a0)),
          cx + (gint32)(r * cosf(a1)), cy + (gint32)(r * sinf(a1)));
    }
    return;
  }

  /* Filled sector: per-pixel angular test */
  gint32 r2 = r * r;
  gfloat sweep = deg1 - deg0;
  gfloat ex0 = cosf(rad0), ey0 = sinf(rad0);
  gfloat ex1 = cosf(rad1), ey1 = sinf(rad1);

  for (gint32 dy = -r; dy <= r; dy++) {
    gint32 rowY = cy + dy;
    gfloat fdy = (gfloat)dy;
    gfloat half = sqrtf(fmaxf(0.f, (gfloat)r2 - fdy * fdy));
    gint32 xl = (gint32)ceilf(-half), xr = (gint32)floorf(half);

    if (sweep >= 360.f) {
      hline(cx + xl, cx + xr, rowY);
      continue;
    }

    gint32 span_l = cx + xr + 1, span_r = cx + xl - 1;
    for (gint32 dx = xl; dx <= xr; dx++) {
      gfloat fdx = (gfloat)dx;
      gfloat cross0 = ex0 * fdy - ey0 * fdx;
      gfloat cross1 = ex1 * fdy - ey1 * fdx;
      gboolean inside = (sweep <= 180.f) ? (cross0 >= 0.f && cross1 <= 0.f)
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

void _prim_rounded_rect(gint32 x, gint32 y, gint32 w, gint32 h, gint32 r,
                        gboolean filled) {
  if (r > w / 2)
    r = w / 2;
  if (r > h / 2)
    r = h / 2;

  if (!filled) {
    SDL_RenderDrawLine(_renderer, x + r, y, x + w - r, y);
    SDL_RenderDrawLine(_renderer, x + r, y + h, x + w - r, y + h);
    SDL_RenderDrawLine(_renderer, x, y + r, x, y + h - r);
    SDL_RenderDrawLine(_renderer, x + w, y + r, x + w, y + h - r);
    _prim_arc(x + r, y + r, r, 180.f, 270.f, FALSE);
    _prim_arc(x + w - r, y + r, r, 270.f, 360.f, FALSE);
    _prim_arc(x + w - r, y + h - r, r, 0.f, 90.f, FALSE);
    _prim_arc(x + r, y + h - r, r, 90.f, 180.f, FALSE);
    return;
  }

  SDL_Rect rects[3] = {
      {x + r, y, w - 2 * r, h},
      {x, y + r, r, h - 2 * r},
      {x + w - r, y + r, r, h - 2 * r},
  };
  SDL_RenderFillRects(_renderer, rects, 3);

  /* Corner centres */
  const gint32 ccx[] = {x + r, x + w - r, x + r, x + w - r};
  const gint32 ccy[] = {y + r, y + r, y + h - r, y + h - r};
  const gint32 sx[] = {-1, 1, -1, 1};
  const gint32 sy[] = {-1, -1, 1, 1};

  gint32 px = r, py = 0, err = 1 - r;
  while (px >= py) {
    for (int c = 0; c < 4; c++) {
      hline(ccx[c], ccx[c] + sx[c] * px, ccy[c] + sy[c] * py);
      hline(ccx[c], ccx[c] + sx[c] * py, ccy[c] + sy[c] * px);
    }
    py++;
    err += (err < 0) ? 2 * py + 1 : (px--, 2 * (py - px) + 1);
  }
}

void _prim_thick_line(gint32 x1, gint32 y1, gint32 x2, gint32 y2, gdouble t) {
  if (t <= 1.0) {
    SDL_RenderDrawLine(_renderer, x1, y1, x2, y2);
    return;
  }

  double dx = x2 - x1, dy = y2 - y1, len = sqrt(dx * dx + dy * dy);
  if (len < 0.5) {
    _prim_circle(x1, y1, (gint32)(t / 2.0), TRUE);
    return;
  }

  double nx = -dy / len * (t / 2.0), ny = dx / len * (t / 2.0);
  SDL_Point pts[4] = {
      {(int)(x1 + nx + .5), (int)(y1 + ny + .5)},
      {(int)(x2 + nx + .5), (int)(y2 + ny + .5)},
      {(int)(x2 - nx + .5), (int)(y2 - ny + .5)},
      {(int)(x1 - nx + .5), (int)(y1 - ny + .5)},
  };
  _prim_polygon(pts, 4, TRUE);
}

void _prim_polygon(SDL_Point *pts, gint32 n, gboolean filled) {
  if (n < 2)
    return;

  for (gint32 i = 0; i < n; i++)
    SDL_RenderDrawLine(_renderer, pts[i].x, pts[i].y, pts[(i + 1) % n].x,
                       pts[(i + 1) % n].y);
  if (!filled || n < 3)
    return;

  gint32 ymin = pts[0].y, ymax = pts[0].y;
  for (gint32 i = 1; i < n; i++) {
    if (pts[i].y < ymin)
      ymin = pts[i].y;
    if (pts[i].y > ymax)
      ymax = pts[i].y;
  }
  if (ymin == ymax)
    return;

  gint32 *xs = g_malloc(n * sizeof(gint32));
  if (!xs)
    return;

  for (gint32 scanY = ymin; scanY <= ymax; scanY++) {
    gint32 cnt = 0;
    for (gint32 i = 0, j = n - 1; i < n; j = i++) {
      gint32 yi = pts[i].y, yj = pts[j].y;
      if ((yi <= scanY && yj > scanY) || (yj <= scanY && yi > scanY))
        xs[cnt++] =
            pts[i].x + (gint32)(((gint64)(scanY - yi) * (pts[j].x - pts[i].x)) /
                                (yj - yi));
    }
    /* Insertion sort */
    for (gint32 a = 1; a < cnt; a++) {
      gint32 v = xs[a], b = a;
      while (b > 0 && xs[b - 1] > v) {
        xs[b] = xs[b - 1];
        b--;
      }
      xs[b] = v;
    }
    for (gint32 a = 0; a + 1 < cnt; a += 2)
      hline(xs[a], xs[a + 1], scanY);
  }
  g_free(xs);
}
