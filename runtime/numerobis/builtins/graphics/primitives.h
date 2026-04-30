#ifndef NUMEROBIS_PRIMITIVES_H
#define NUMEROBIS_PRIMITIVES_H

#include <SDL2/SDL.h>
#include <stdbool.h>

void _prim_circle(int cx, int cy, int r, bool filled);
void _prim_ellipse(int cx, int cy, int rx, int ry, bool filled);
void _prim_arc(int cx, int cy, int r, float deg0, float deg1, bool filled);
void _prim_rounded_rect(int x, int y, int w, int h, int r, bool filled);
void _prim_thick_line(int x1, int y1, int x2, int y2, double t);
void _prim_polygon(SDL_Point *pts, int n, bool filled, bool closed);
#endif
