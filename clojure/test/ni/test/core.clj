(ns ni.test.core
  (:use ni.core)
  (:use clojure.test)
  (:use [clojure.java.io :only [input-stream]])
  )


(def hwtxt "test/ni/test/hw.txt")
(def tcd-spki "test/ni/test/tcd.spki")


;; the ni name for hw.txt according to the I-D
(def hwname1 "ni:///sha-256;f4OxZX_x_FO5LcGBSKHWXfwtSx-j1ncoSt3SABJtkGk")

;; same as above but s/f/e/ in 1st character of hash
(def badname1 "ni:///sha-256;e4OxZX_x_FO5LcGBSKHWXfwtSx-j1ncoSt3SABJtkGk")

;; same as above but deleted a character of hash
(def badname2 "ni:///sha-256;f4OxZX_x_FO5LcGBSKHWXfwtSx-j1ncoSt3SABJtkG")

;; the ni name for tcd.spki
(def pname1 "ni:///sha-256;UyaQV-Ev4rdLoHyJJWCi11OHfrYv9E1aGQAlMO2X_-Q")

;; the binary suite 3 name for tcd.spki
(def bname1 "0353269057e12fe2b74ba07c892560a2")

;; human form 96 bit truncated hash of hw.txt
(def nihname1 "nih:4;7f83b1657ff1fc53b92dc181;2")

;; human form 120 bit truncated hash of hw.txt, with string form name
(def nihname2 "nih:sha-256-120;7f83b1657ff1fc53b92dc18148a1d6;8")

;; human form 120 bit truncated hash of hw.txt, with string form name
(def nihname3 "nih:3;7f83b1657ff1fc53b92dc18148a1d6;8")

;; ni URI for tcd.spki truncated to 32 bits with a query string
(def hwname2 "ni://tcd.ie/sha-256-32;UyaQVw?foo=bar")




(defn mkni-string [input auth algo paras]
  (ni-toString (mkni input auth algo paras)))


(def name-hw
  (mkni-string (input-stream hwtxt) "" "sha-256" ""))


(def name-tcd-spki
  (mkni-string (input-stream tcd-spki) "" "sha-256" ""))



(deftest test-ni-hw
  (is (= hwname1 name-hw)))


(deftest test-ni-tcd-spki
  (is (= pname1 name-tcd-spki)))


(deftest test-badres1
  (let [badni1 (ni badname1)]
    (is (not (valid? badni1 (input-stream hwtxt))))))


(deftest test-badres2
  (let [badni2 (ni badname2)]
    (is (not (valid? badni2 (input-stream hwtxt))))))


(deftest test-goodres1
  (let [goodni1 (ni hwname1)]
    (is (valid? goodni1 (input-stream hwtxt)))))

(deftest test-goodres2
  (let [goodni2 (ni hwname2)]
    (is (valid? goodni2 (input-stream tcd-spki)))))

(deftest test-binname
  (let [binname
        (hexify-bytes (ni-toBin
                 (mkni (input-stream tcd-spki) "" "sha-256-120" "")))]
    (is (= binname bname1))))

(deftest test-nihout1
  (let [nihout1 (mkni (input-stream hwtxt) "" "sha-256-96" "")]
    (is (= nihname1 (ni-toNih nihout1)))))


(deftest test-nihout2
  (let [nihout2 (mkni (input-stream hwtxt) "" "sha-256-120" "")]
    (is (= nihname3 (ni-toNih nihout2)))))





