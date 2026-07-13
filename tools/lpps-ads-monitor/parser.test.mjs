import assert from "node:assert/strict";
import { parseAdsLine } from "./parser.js";

const diag = parseAdsLine("[00:00:01.000,000] <inf> analog_axis_hires: analog_axis_hires_0: ch0:-42 ch1:17 axis0:-40 axis1:15 out0:0 out1:1", 100);
assert.equal(diag.source, "diag");
assert.equal(diag.ch0, -42);
assert.equal(diag.ch1, 17);
assert.equal(diag.out1, 1);

const csv = parseAdsLine("ADSCSV,1234,4000000,3990000,-12,34,0,1", 200);
assert.equal(csv.source, "csv");
assert.equal(csv.raw0, 4000000);
assert.equal(csv.ch1, 34);

const csv4 = parseAdsLine("ADSCSV4,1234,10,20,30,40,-1,-2,-3,-4,1,2,3,4", 300);
assert.equal(csv4.source, "csv4");
assert.equal(csv4.raw3, 40);
assert.equal(csv4.ch2, -3);
assert.equal(csv4.out3, 4);

assert.equal(parseAdsLine("unrelated log line"), null);
console.log("parser tests: OK");
