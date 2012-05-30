;; NI URI creation, parsing and validation

;; This is the NI URI library developed as
;; part of the SAIL project. (http://sail-project.eu)

;; Specification(s) - note, versions may change::
;; * http://tools.ietf.org/html/farrell-decade-ni
;; * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params

;; Author:: Dirk Kutscher <kutscher@neclab.eu>
;; Copyright:: Copyright (c) 2012 Dirk Kutscher <kutscher@neclab.eu>

;; License:: http://www.apache.org/licenses/LICENSE-2.0.html
;; Licensed under the Apache License, Version 2.0 (the "License");
;; you may not use this file except in compliance with the License.
;; You may obtain a copy of the License at

;;       http://www.apache.org/licenses/LICENSE-2.0

;; Unless required by applicable law or agreed to in writing, software
;; distributed under the License is distributed on an "AS IS" BASIS,
;; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
;; See the License for the specific language governing permissions and
;; limitations under the License.
;;
;; Examples:
;;
;; parsing:
;; (ni "ni://example.com/sha-256;abcd?ct=image/jpg")
;;
;; creation:
;; (def name1 (mkni "this is the NDO data" "example.com" "sha-256" "ct=text/plain"))
;; (def name2 (mkni  file "sha-256" ""))
;;
;; validation:
;; (valid? name2 file)
;; (valid? name1 "foo")
;;
;; string transformation:
;; (ni-toString name1)
;;
;; transforming to NIH format:
;; (ni-toNih name1)
;;
;; creating NI URI from NIH in string representation:
;; (nih "nih:sha-256-120;7f83b1657ff1fc53b92dc18148a1d6;8")
;;
;; transforming NI URI to binary format:
;; (ni-toBin name1)
;;
;; create NI URI from binary representation (byteArray):
;; (niBin bits)


(ns ni.core

(:require [clojure.data.codec.base64 :as b64]
           [clojure.java.io :as io]
           [clojure.string :as string]
           [clj-message-digest.core]
           [clj-message-digest.core :as msg]
           [clj-http.client :as client]
           )
)



(defn urlencode [s]
  (string/escape s {\+ \- \/ \_ \= ""}))

(defn urldecode [s]
  (let [res  (string/escape s {\- \+ \_ \/})
        padcount (- 4 (mod (count res) 4))
        pad (reduce str (take padcount (repeat "=")))]
    (str res pad)))
    
    


(defn b64urlencode [s]
    (let [base64 (String. (b64/encode s))]
    (urlencode base64)
  ))


(defn b64urldecode [s]
  (let [base64 (urldecode s)]
    (b64/decode (.getBytes base64))
  ))



(defn hexify-bytes [bytes]
  (apply str (map #(format "%02x" %) bytes)))

(defn hexify [s]
  (hexify-bytes (.getBytes s "UTF-8")))


(defn unhexify-bytes [s]
  (into-array Byte/TYPE
              (map (fn [[x y]]
                    (unchecked-byte (Integer/parseInt (str x y) 16)))
                       (partition 2 s))))


(defn unhexify [s]
  (let [bytes (unhexify-bytes s)]
    (String. bytes "UTF-8")))


(defn luhn-calc-addend [c base factor]
  (let [codepoint  (Integer/parseInt (str c) base)
        addend (* factor codepoint)]
    (+ (quot addend base) (mod addend base))))


(defn luhn16 [s]
  "Luhn's algorithm (http://en.wikipedia.org/wiki/Luhn_mod_N_algorithm)"
  (let [
        base 16
        sum (reduce + (map #(luhn-calc-addend %1 base %2) (reverse s) (cycle [2 1])))
        remainder (mod sum base)
        check-code-point (mod (- base remainder) base)
        ]
    (Integer/toHexString check-code-point)
))


(defn truncate-hash [hash nrbits]
  "truncate the specified hash value to nrbits length"
  (into-array Byte/TYPE (take (/ nrbits 8) hash))
)


;; this is how you would define it by hand -- but we generate it below
;; (defn sha256-32 [input]
;;   (truncate-hash (msg/digest "sha-256" input) 32))


(defn make-trunc-hash-fn [base nrbits]
  (fn [input] (truncate-hash (msg/digest base input) nrbits)))


(defn mk-hash-funcs [base trunc-specs]
  "create a map {hash-algo-name hash-trunc-func}"
  (let [
        funcs (map #(make-trunc-hash-fn base %) trunc-specs)
        names (map #(str base "-" %) trunc-specs)
        ]
    (zipmap names funcs)))


(def sha-256
  (fn [input] (msg/digest "sha-256" input)))

(def hash-funcs
  "define truncated and the non-truncated versions of sha-256"
  (assoc
      (mk-hash-funcs "sha-256" [128 120 96 64 32])
    "sha-256" sha-256))


(def hash-names
  "the list of supported hash algorithms"
  {0 "Reserved"
   1 "sha-256"
   2 "sha-256-128"
   3  "sha-256-120"
   4  "sha-256-96"
   5  "sha-256-64"
   6  "sha-256-32"
   32 "Reserved"})

(def hash-ids
  "the mapping from hash algo name to number"
  (zipmap (vals hash-names) (keys hash-names)))


(defrecord Uri [scheme host local paras])
(defrecord NiUri [scheme auth hash-algo hash-digest paras])

(defn uri-elements [str]
  "Tries to parse the string argument using the regular expression
provided by http://tools.ietf.org/html/rfc3986#appendix-B. Returns a
lazy sequence containing the array of the URI components"
  (re-seq #"^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?" str))


(defn uri [str]
  "Creates an Uri record from the string argument"
  (let [[uri s scheme h host local p paras]
        (first (uri-elements str))]
    (->Uri scheme host local paras)))

(defn hash-data [local-part]
  "call Java's string split and returns Java collection of strings"
  (.split local-part ";"))


(defn ni [str]
  "Creates an NI URI from the string argument"
  (let [u (uri str)
        [hash-algo hash-digest] (hash-data (:local u))]
    (->NiUri (:scheme u) (:host u) (first (rest (.split hash-algo "/"))) (b64urldecode hash-digest) (:paras u))
    ))


(defn mkhash [algo input]
  ((get hash-funcs algo sha-256) input))

(defn dohash [ni-uri input]
  (mkhash (:hash-algo ni-uri) input))


(defn valid? [ni-uri input]
  "return true if the specified NI URI is bound to the input data"
    (java.util.Arrays/equals (dohash ni-uri input) (:hash-digest ni-uri)))

(defn mkni [input auth algo paras]
  "create NI URI for specified input data"
  (->NiUri "ni" auth algo (mkhash algo input) paras))


(defn ni-urlSegment [ni-uri]
  "return urlSegment representation"
    (str (:hash-algo ni-uri) ";" (b64urlencode (:hash-digest ni-uri))))

(defn ni-toString [ni-uri]
  "return string representation"
  (let [
        p (:paras ni-uri)
        pp (if p p "")
        paras (if (.equals pp "") "" (str "?" pp))]
    (str "ni://" (:auth ni-uri) "/" (ni-urlSegment ni-uri) paras)))


(defn ni-toNih [ni-uri]
  "transform to nih format"
  (let [hexhash (hexify-bytes (:hash-digest ni-uri))]
    (str "nih:" (get hash-ids (:hash-algo ni-uri) 0) ";" hexhash ";" (luhn16 hexhash))
    ))


(defn nih-components [s]
  "return NIH URI components in string s"
  (let [[scheme data] (clojure.string/split s #"\:")]
    (clojure.string/split data #"\;")
    ))

(defn nih [s]
  "create NI URI from NIH URI in string representation"
  (let [[algo hash checksum] (nih-components s)]
    (->NiUri "ni" nil algo (unhexify-bytes hash) nil)
  ))

(defn nih-ckecksum-valid? [s]
  "check the checksum"
  (let [[algo hash checksum] (nih-components s)]
    (== 0 (compare checksum (luhn16 hash)))
  ))


(defn ni-toBin [ni]
  "transform NI URI to binary representation"
  (let [hash-id (get hash-ids (:hash-algo ni) 0)]
    (byte-array (map byte (cons hash-id (:hash-digest ni))))
  ))

(defn niBin [data]
  "create NI URI from binary representation (byteArray)"
  (let [algo (first data)
        hash (byte-array (rest data))]
    (->NiUri "ni" nil (get hash-names algo "Reserved") hash nil)
  ))



(def get-path "/netinfproto/get")
(def pub-path "/netinfproto/publish")


(defn ni-get [uri msgid & loc]
  (let [http-uri (str "http://" (first loc) get-path)]
    (
     (client/post http-uri
                  {:form-params {:URI uri,
                                 :msgid msgid,
                                 :ext "no extension"}}) :body)))



(defn ni-pub [uri data msgid & loc]
  (let [http-uri (str "http://" (first loc) pub-path)]

    (client/post http-uri {:multipart [["URI" uri]
                                       ["msgid" msgid]
                                       ["octets" data]
                                       ["fullPut" "yes"]]
                           :retry-handler (fn [ex try-count http-context]
                                            (println "Got:" ex)
                                            (if (> try-count 4) false true))})))



