;; NI URI creation, parsing and validation

;; This is the NI URI library developed as
;; part of the SAIL project. (http://sail-project.eu)

;; Specification(s) - note, versions may change::
;; * http://tools.ietf.org/html/farrell-decade-ni-00
;; * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-00

;; Author:: Dirk Kutscher <kutscher@neclab.eu>
;; Copyright:: Copyright (c) 2012 Dirk Kutscher <kutscher@neclab.eu>
;; Specification:: http://tools.ietf.org/html/draft-farrell-decade-ni-00

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

(ns ni

(:require [clojure.data.codec.base64 :as b64]
           [clojure.java.io :as io]
           [clojure.string :as string]
           [clj-message-digest.core]
           [clj-message-digest.core :as msg])
)



(defn urlencode [str]
  (string/escape str {\+ \- \/ \_ \= ""}))

(defn urldecode [str]
  (string/escape str {\- \+ \_ \/}))


(defn b64urlencode [str]
  (let [base64 (String. (b64/encode str))]
    (urlencode base64)
  ))


(defn b64urldecode [str]
  (let [base64 (urldecode str)]
    (String. (b64/decode (.getBytes base64)))
  ))


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
    (->NiUri (:scheme u) (:host u) (rest (.split hash-algo "/")) (b64urldecode hash-digest) (:paras u))
    ))


(defn hash-algo [ni-uri]
  "get the hash algorithm of the NI URI in upper case"
  (.toUpperCase (:hash-algo ni-uri)))
  

(defn valid? [ni-uri input]
  "return true if the specified NI URI is bound to the input data"
  (let [hash (msg/digest (hash-algo ni-uri) input)]
    (java.util.Arrays/equals hash (:hash-digest ni-uri))))

(defn mkni [input auth algo paras]
  "create NI URI for specified input data"
  (let [hash (msg/digest (.toUpperCase algo) input)]
    (->NiUri "ni" auth algo hash paras)
    ))


(defn ni-toString [ni-uri]
  "return string representation"
  (let [
        p (:paras ni-uri)
        pp (if p p "")
        paras (if (.equals pp "") "" (str "?" pp))]
    (str "ni://" (:auth ni-uri) "/" (:hash-algo ni-uri) ";" (b64urlencode (:hash-digest ni-uri)) paras)))


(def get-path "/.well-known/netinfproto/get")
(def pub-path "/.well-known/netinfproto/publish")


(defn ni-get [uri msgid & loc]
  (let [http-uri (str "http://" (first loc) get-path)]
    (
     (println http-uri)
     (client/post http-uri
                  {:form-params {:URI uri,
                                 :msgid msgid,
                                 :ext "no extension"}}) :body)))


