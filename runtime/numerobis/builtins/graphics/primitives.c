#include "state.h"

#include <SDL2/SDL.h>
#include <glib.h>
#include <math.h>

void _prim_circle(gint32 cx, gint32 cy, gint32 r, gboolean filled) {
  gint32 x = r, y = 0, err = 0;
  while (x >= y) {
    if (filled) {
      SDL_RenderDrawLine(_renderer, cx - x, cy + y, cx + x, cy + y);
      SDL_RenderDrawLine(_renderer, cx - x, cy - y, cx + x, cy - y);
      SDL_RenderDrawLine(_renderer, cx - y, cy + x, cx + y, cy + x);
      SDL_RenderDrawLine(_renderer, cx - y, cy - x, cx + y, cy - x);
    } else {
      SDL_RenderDrawPoint(_renderer, cx + x, cy + y);
      SDL_RenderDrawPoint(_renderer, cx - x, cy + y);
      SDL_RenderDrawPoint(_renderer, cx + x, cy - y);
      SDL_RenderDrawPoint(_renderer, cx - x, cy - y);
      SDL_RenderDrawPoint(_renderer, cx + y, cy + x);
      SDL_RenderDrawPoint(_renderer, cx - y, cy + x);
      SDL_RenderDrawPoint(_renderer, cx + y, cy - x);
      SDL_RenderDrawPoint(_renderer, cx - y, cy - x);
    }
    y++;
    if (err <= 0)
      err += 2 * y + 1;
    if (err > 0) {
      x--;
      err -= 2 * x + 1;
    }
  }
}

void _prim_ellipse(gint32 cx, gint32 cy, gint32 rx, gint32 ry,
                   gboolean filled) {
  double h = (double)(rx - ry) * (rx - ry) / ((double)(rx + ry) * (rx + ry));
  int segs = (int)fmax(64, M_PI * (rx + ry) *
                               (1 + 3 * h / (10 + sqrt(4 - 3 * h))) / 2.0);
  for (int s = 0; s < segs; s++) {
    double a0 = 2.0 * M_PI * s / segs, a1 = 2.0 * M_PI * (s + 1) / segs;
    gint32 x0 = cx + (gint32)(rx * cos(a0)), y0 = cy + (gint32)(ry * sin(a0));
    gint32 x1 = cx + (gint32)(rx * cos(a1)), y1 = cy + (gint32)(ry * sin(a1));
    SDL_RenderDrawLine(_renderer, x0, y0, x1, y1);
    if (filled) {
      SDL_RenderDrawLine(_renderer, cx, cy, x0, y0);
      SDL_RenderDrawLine(_renderer, cx, cy, x1, y1);
    }
  }
}

void _prim_arc(gint32 cx, gint32 cy, gint32 r, gfloat deg0, gfloat deg1,
               gboolean filled) {
  gfloat rad0 = deg0 * (gfloat)M_PI / 180.f, rad1 = deg1 * (gfloat)M_PI / 180.f;
  int segs = (int)fmax(16, fabsf(deg1 - deg0) / 2.f);
  gfloat step = (rad1 - rad0) / segs;
  for (int s = 0; s < segs; s++) {
    gfloat a0 = rad0 + step * s, a1 = rad0 + step * (s + 1);
    gint32 x0 = cx + (gint32)(r * cosf(a0)), y0 = cy + (gint32)(r * sinf(a0));
    gint32 x1 = cx + (gint32)(r * cosf(a1)), y1 = cy + (gint32)(r * sinf(a1));
    SDL_RenderDrawLine(_renderer, x0, y0, x1, y1);
    if (filled) {
      SDL_RenderDrawLine(_renderer, cx, cy, x0, y0);
      SDL_RenderDrawLine(_renderer, cx, cy, x1, y1);
    }
  }
}

void _prim_rounded_rect(gint32 x, gint32 y, gint32 w, gint32 h, gint32 r,
                        gboolean filled) {
  SDL_RenderDrawLine(_renderer, x + r, y, x + w - r, y);
  SDL_RenderDrawLine(_renderer, x + r, y + h, x + w - r, y + h);
  SDL_RenderDrawLine(_renderer, x, y + r, x, y + h - r);
  SDL_RenderDrawLine(_renderer, x + w, y + r, x + w, y + h - r);

  _prim_arc(x + r, y + r, r, 180.f, 270.f, FALSE);
  _prim_arc(x + w - r, y + r, r, 270.f, 360.f, FALSE);
  _prim_arc(x + w - r, y + h - r, r, 0.f, 90.f, FALSE);
  _prim_arc(x + r, y + h - r, r, 90.f, 180.f, FALSE);

  if (filled) {
    SDL_Rect rects[3] = {
        {x + r, y, w - 2 * r, h},
        {x, y + r, r, h - 2 * r},
        {x + w - r, y + r, r, h - 2 * r},
    };
    SDL_RenderFillRects(_renderer, rects, 3);
    for (gint32 dy = 0; dy <= r; dy++) {
      gint32 dx = (gint32)sqrt((double)(r * r - dy * dy));
      SDL_RenderDrawLine(_renderer, x + r - dx, y + r - dy, x + r, y + r - dy);
      SDL_RenderDrawLine(_renderer, x + w - r, y + r - dy, x + w - r + dx,
                         y + r - dy);
      SDL_RenderDrawLine(_renderer, x + r - dx, y + h - r + dy, x + r,
                         y + h - r + dy);
      SDL_RenderDrawLine(_renderer, x + w - r, y + h - r + dy, x + w - r + dx,
                         y + h - r + dy);
    }
  }
}

void _prim_thick_line(gint32 x1, gint32 y1, gint32 x2, gint32 y2, gdouble t) {
  if (t <= 1.0) {
    SDL_RenderDrawLine(_renderer, x1, y1, x2, y2);
    return;
  }
  double dx = x2 - x1, dy = y2 - y1, len = sqrt(dx * dx + dy * dy);
  if (len < 0.001)
    return;
  double nx = -dy / len, ny = dx / len;
  int half = (int)(t / 2.0);
  for (int k = -half; k <= half; k++)
    SDL_RenderDrawLine(_renderer, (int)(x1 + nx * k), (int)(y1 + ny * k),
                       (int)(x2 + nx * k), (int)(y2 + ny * k));
}

void _prim_polygon(SDL_Point *pts, gint32 n, gboolean filled) {
  for (gint32 i = 0; i < n - 1; i++)
    SDL_RenderDrawLine(_renderer, pts[i].x, pts[i].y, pts[i + 1].x,
                       pts[i + 1].y);
  SDL_RenderDrawLine(_renderer, pts[n - 1].x, pts[n - 1].y, pts[0].x, pts[0].y);
  if (filled)
    for (gint32 i = 1; i < n - 1; i++) {
      SDL_RenderDrawLine(_renderer, pts[0].x, pts[0].y, pts[i].x, pts[i].y);
      SDL_RenderDrawLine(_renderer, pts[0].x, pts[0].y, pts[i + 1].x,
                         pts[i + 1].y);
    }
}
