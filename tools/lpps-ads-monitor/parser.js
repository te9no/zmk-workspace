const ANSI_PATTERN = /\x1b\[[0-9;]*m/g;

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseAdsLine(input, receivedAt = performance.now()) {
  const line = input.replace(ANSI_PATTERN, "").trim();
  if (!line) return null;

  const csv4 = line.match(/(?:^|\s)ADSCSV4,\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)/);
  if (csv4) {
    return {
      source: "csv4",
      deviceMs: number(csv4[1]),
      raw0: number(csv4[2]), raw1: number(csv4[3]),
      raw2: number(csv4[4]), raw3: number(csv4[5]),
      ch0: number(csv4[6]), ch1: number(csv4[7]),
      ch2: number(csv4[8]), ch3: number(csv4[9]),
      out0: number(csv4[10]), out1: number(csv4[11]),
      out2: number(csv4[12]), out3: number(csv4[13]),
      receivedAt,
      line,
    };
  }

  const csv = line.match(/(?:^|\s)ADSCSV,\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)/);
  if (csv) {
    return {
      source: "csv",
      deviceMs: number(csv[1]),
      raw0: number(csv[2]),
      raw1: number(csv[3]),
      ch0: number(csv[4]),
      ch1: number(csv[5]),
      out0: number(csv[6]),
      out1: number(csv[7]),
      receivedAt,
      line,
    };
  }

  const diag = line.match(/analog_axis_hires(?:_0)?:\s+ch0:(-?\d+)\s+ch1:(-?\d+)\s+axis0:(-?\d+)\s+axis1:(-?\d+)\s+out0:(-?\d+)\s+out1:(-?\d+)/);
  if (diag) {
    return {
      source: "diag",
      raw0: null,
      raw1: null,
      ch0: number(diag[1]),
      ch1: number(diag[2]),
      axis0: number(diag[3]),
      axis1: number(diag[4]),
      out0: number(diag[5]),
      out1: number(diag[6]),
      receivedAt,
      line,
    };
  }

  const rawDelta = line.match(/analog raw_delta\s+ch0:(-?\d+)\s+ch1:(-?\d+)/);
  if (rawDelta) {
    return {
      source: "raw_delta",
      raw0: null,
      raw1: null,
      ch0: number(rawDelta[1]),
      ch1: number(rawDelta[2]),
      out0: null,
      out1: null,
      receivedAt,
      line,
    };
  }

  return null;
}
