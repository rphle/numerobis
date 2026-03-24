#ifndef NUMEROBIS_PRIMITIVES_H
#define NUMEROBIS_PRIMITIVES_H

#include <SDL2/SDL.h>
#include <glib.h>

void _prim_circle(gint32 cx, gint32 cy, gint32 r, gboolean filled);
void _prim_ellipse(gint32 cx, gint32 cy, gint32 rx, gint32 ry, gboolean filled);
void _prim_arc(gint32 cx, gint32 cy, gint32 r, gfloat deg0, gfloat deg1,
               gboolean filled);
void _prim_rounded_rect(gint32 x, gint32 y, gint32 w, gint32 h, gint32 r,
                        gboolean filled);
void _prim_thick_line(gint32 x1, gint32 y1, gint32 x2, gint32 y2, gdouble t);
void _prim_polygon(SDL_Point *pts, gint32 n, gboolean filled);

#endif
