/* Archie's handout scanner (phone): find the page, straighten it, clean it up, and make a PDF. All on the phone. */
(function () {
  "use strict";

  // ---- find the page: the biggest bright shape (paper) in a small copy of the photo -----------------------
  function detect(canvas) {
    var W = 320, H = Math.max(1, Math.round(canvas.height * W / canvas.width));
    var c = document.createElement("canvas"); c.width = W; c.height = H;
    var x = c.getContext("2d"); x.drawImage(canvas, 0, 0, W, H);
    var px = x.getImageData(0, 0, W, H).data, g = new Uint8Array(W * H), hist = new Array(256).fill(0), i;
    for (i = 0; i < W * H; i++) { var v = (px[i * 4] * 0.3 + px[i * 4 + 1] * 0.59 + px[i * 4 + 2] * 0.11) | 0; g[i] = v; hist[v]++; }
    // Otsu: the brightness that best splits paper from the table
    var sum = 0, sumB = 0, wB = 0, best = 0, th = 128;
    for (i = 0; i < 256; i++) sum += i * hist[i];
    for (i = 0; i < 256; i++) {
      wB += hist[i]; if (!wB) continue; var wF = W * H - wB; if (!wF) break;
      sumB += i * hist[i]; var mB = sumB / wB, mF = (sum - sumB) / wF, between = wB * wF * (mB - mF) * (mB - mF);
      if (between > best) { best = between; th = i; }
    }
    // the largest bright blob
    var seen = new Uint8Array(W * H), bestPix = null, q = new Int32Array(W * H);
    for (var s = 0; s < W * H; s++) {
      if (seen[s] || g[s] <= th) continue;
      var head = 0, tail = 0, pix = []; q[tail++] = s; seen[s] = 1;
      while (head < tail) {
        var p = q[head++]; pix.push(p); var py = (p / W) | 0, pxx = p % W;
        var nb = [pxx > 0 ? p - 1 : -1, pxx < W - 1 ? p + 1 : -1, py > 0 ? p - W : -1, py < H - 1 ? p + W : -1];
        for (var k = 0; k < 4; k++) { var n = nb[k]; if (n >= 0 && !seen[n] && g[n] > th) { seen[n] = 1; q[tail++] = n; } }
      }
      if (!bestPix || pix.length > bestPix.length) bestPix = pix;
    }
    var area = bestPix ? bestPix.length / (W * H) : 0;
    if (!bestPix || area < 0.12 || area > 0.985) return inset(canvas.width, canvas.height);
    var tl, tr, br, bl, sMin = 1e9, sMax = -1e9, dMin = 1e9, dMax = -1e9;
    bestPix.forEach(function (p) {
      var yy = (p / W) | 0, xx = p % W, su = xx + yy, di = xx - yy;
      if (su < sMin) { sMin = su; tl = [xx, yy]; } if (su > sMax) { sMax = su; br = [xx, yy]; }
      if (di > dMax) { dMax = di; tr = [xx, yy]; } if (di < dMin) { dMin = di; bl = [xx, yy]; }
    });
    var k2 = canvas.width / W;
    return [tl, tr, br, bl].map(function (pt) { return [pt[0] * k2, pt[1] * k2]; });
  }
  function inset(w, h) { var a = w * 0.06, b = h * 0.06; return [[a, b], [w - a, b], [w - a, h - b], [a, h - b]]; }

  // ---- straighten: map the four corners onto a flat page -------------------------------------------------------
  function homography(src, dst) {     // 3x3 that maps dst -> src (so we can sample the photo for each output pixel)
    var A = [], b = [];
    for (var i = 0; i < 4; i++) {
      var X = dst[i][0], Y = dst[i][1], x = src[i][0], y = src[i][1];
      A.push([X, Y, 1, 0, 0, 0, -x * X, -x * Y]); b.push(x);
      A.push([0, 0, 0, X, Y, 1, -y * X, -y * Y]); b.push(y);
    }
    for (var c = 0; c < 8; c++) {                    // Gaussian elimination
      var piv = c; for (var r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
      var t = A[c]; A[c] = A[piv]; A[piv] = t; t = b[c]; b[c] = b[piv]; b[piv] = t;
      for (r = 0; r < 8; r++) if (r !== c) { var f = A[r][c] / A[c][c]; for (var k = c; k < 8; k++) A[r][k] -= f * A[c][k]; b[r] -= f * b[c]; }
    }
    var h = b.map(function (v, i) { return v / A[i][i]; }); h.push(1); return h;
  }
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }
  function flatten(canvas, quad, maxSide) {
    maxSide = maxSide || 1800;
    var w = Math.max(dist(quad[0], quad[1]), dist(quad[3], quad[2])), h = Math.max(dist(quad[0], quad[3]), dist(quad[1], quad[2]));
    var sc = Math.min(1, maxSide / Math.max(w, h)), OW = Math.max(50, Math.round(w * sc)), OH = Math.max(50, Math.round(h * sc));
    var H = homography(quad, [[0, 0], [OW, 0], [OW, OH], [0, OH]]);
    var sp = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height), S = sp.data, SW = canvas.width, SH = canvas.height;
    var out = document.createElement("canvas"); out.width = OW; out.height = OH;
    var ox = out.getContext("2d"), od = ox.createImageData(OW, OH), D = od.data;
    for (var y = 0; y < OH; y++) for (var x = 0; x < OW; x++) {
      var den = H[6] * x + H[7] * y + 1, sx = (H[0] * x + H[1] * y + H[2]) / den, sy = (H[3] * x + H[4] * y + H[5]) / den;
      var x0 = Math.floor(sx), y0 = Math.floor(sy), fx = sx - x0, fy = sy - y0, o = (y * OW + x) * 4;
      if (x0 < 0 || y0 < 0 || x0 >= SW - 1 || y0 >= SH - 1) { D[o] = D[o + 1] = D[o + 2] = 255; D[o + 3] = 255; continue; }
      var i00 = (y0 * SW + x0) * 4, i10 = i00 + 4, i01 = i00 + SW * 4, i11 = i01 + 4;
      for (var ch = 0; ch < 3; ch++) D[o + ch] = (S[i00 + ch] * (1 - fx) + S[i10 + ch] * fx) * (1 - fy) + (S[i01 + ch] * (1 - fx) + S[i11 + ch] * fx) * fy;
      D[o + 3] = 255;
    }
    enhance(D);
    ox.putImageData(od, 0, 0);
    return out;
  }
  // ---- clean up: paper goes white, ink goes dark (levels from the page itself) --------------------------------
  function enhance(D) {
    var hist = new Array(256).fill(0), n = D.length / 4, i;
    for (i = 0; i < D.length; i += 16) hist[(D[i] * 0.3 + D[i + 1] * 0.59 + D[i + 2] * 0.11) | 0]++;
    var tot = 0; hist.forEach(function (c) { tot += c; });
    var acc = 0, lo = 0, hi = 255;
    for (i = 0; i < 256; i++) { acc += hist[i]; if (acc > tot * 0.02) { lo = i; break; } }
    acc = 0; for (i = 255; i >= 0; i--) { acc += hist[i]; if (acc > tot * 0.25) { hi = i; break; } }   // most of a page is paper
    if (hi - lo < 40) return;
    var k = 255 / (hi - lo);
    for (i = 0; i < D.length; i += 4) for (var ch = 0; ch < 3; ch++) { var v = (D[i + ch] - lo) * k; D[i + ch] = v < 0 ? 0 : v > 255 ? 255 : v; }
  }

  // ---- the PDF: one page per photo, letter width, the JPEGs inside as they are ---------------------------------
  function pdf(pages) {        // pages: [{jpeg: Uint8Array, w, h}]
    var enc = new TextEncoder(), parts = [], offs = [], len = 0;
    function add(x) { var b = typeof x === "string" ? enc.encode(x) : x; parts.push(b); len += b.length; }
    function obj(n, body) { offs[n] = len; add(n + " 0 obj\n"); body(); add("\nendobj\n"); }
    add("%PDF-1.4\n%âãÏÓ\n");
    var N = pages.length, kids = [];
    for (var i = 0; i < N; i++) kids.push((3 + i * 3) + " 0 R");
    obj(1, function () { add("<< /Type /Catalog /Pages 2 0 R >>"); });
    obj(2, function () { add("<< /Type /Pages /Count " + N + " /Kids [" + kids.join(" ") + "] >>"); });
    pages.forEach(function (p, i) {
      var pn = 3 + i * 3, PW = 612, PH = Math.round(612 * p.h / p.w);
      var cs = "q " + PW + " 0 0 " + PH + " 0 0 cm /Im0 Do Q";
      obj(pn, function () { add("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + PW + " " + PH + "] /Resources << /XObject << /Im0 " + (pn + 1) + " 0 R >> >> /Contents " + (pn + 2) + " 0 R >>"); });
      obj(pn + 1, function () { add("<< /Type /XObject /Subtype /Image /Width " + p.w + " /Height " + p.h + " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length " + p.jpeg.length + " >>\nstream\n"); add(p.jpeg); add("\nendstream"); });
      obj(pn + 2, function () { add("<< /Length " + cs.length + " >>\nstream\n" + cs + "\nendstream"); });
    });
    var xref = len, total = 3 + N * 3;
    add("xref\n0 " + total + "\n0000000000 65535 f \n");
    for (i = 1; i < total; i++) add(("0000000000" + offs[i]).slice(-10) + " 00000 n \n");
    add("trailer\n<< /Size " + total + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF\n");
    return new Blob(parts, { type: "application/pdf" });
  }

  window.ArchieScan = { detect: detect, flatten: flatten, pdf: pdf, inset: inset };
})();
