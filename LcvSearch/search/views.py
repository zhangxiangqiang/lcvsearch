import json

from bs4 import BeautifulSoup
from django.shortcuts import render
from django.views.generic.base import View
from search.models import ArticleType
from django.http import HttpResponse
from elasticsearch import Elasticsearch
from datetime import datetime
import redis

client = Elasticsearch(hosts=["127.0.0.1"])
redis_cli = redis.StrictRedis()


class IndexView(View):
    #首页
    def get(self, request):
        topn_search = redis_cli.zrevrangebyscore("search_keywords_set", "+inf", "-inf", start=0, num=5)
        return render(request, "index.html", {"topn_search":topn_search})

        # return render(request, "index.html")

# Create your views here.
class SearchSuggest(View):
    def get(self, request):
        key_words = request.GET.get('s','')
        re_datas = []
        if key_words:
            s = ArticleType.search()
            s = s.suggest('my_suggest', key_words, completion={
                "field":"suggest", "fuzzy":{
                    "fuzziness":2
                },
                "size": 10
            })
            suggestions = s.execute_suggest()
            for match in suggestions.my_suggest[0].options:
                source = match._source
                re_datas.append(source["title"])
        return HttpResponse(json.dumps(re_datas), content_type="application/json")


class SearchView(View):
    def get(self, request):
        key_words = request.GET.get("q","")
        s_type = request.GET.get("s_type", "article")

        redis_cli.zincrby("search_keywords_set", key_words)

        topn_search = redis_cli.zrevrangebyscore("search_keywords_set", "+inf", "-inf", start=0, num=5)
        page = request.GET.get("p", "1")
        try:
            page = int(page)
        except:
            page = 1
        start_time = datetime.now()
        if s_type == "article":
            site = "伯乐在线"
            count = redis_cli.get("jobbole_count")
            response = client.search(
                index= "jobbole",
                body={
                    "query":{
                        "multi_match":{
                            "query":key_words,
                            "fields":["tags", "title", "content"]
                        }
                    },
                    "from":(page-1)*10,
                    "size":10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                            "tags": {},
                        }
                    }
                }
            )
        if s_type == "question":
            site = "知乎"
            count = redis_cli.get("zhihu_count")
            start_time = datetime.now()
            response = client.search(
                index="zhihu",
                doc_type="question",
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": ["title", "topics", "content"]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                            "topics": {},
                        }
                    }
                }
            )
        if s_type == "job":
            site = "拉勾"
            count = redis_cli.get("job_count")
            start_time = datetime.now()
            response = client.search(
                index="lagou",
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": ["title", "tags", "job_desc"]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "job_desc": {},
                            "tags": {},
                        }
                    }
                }
            )

        end_time = datetime.now()
        last_seconds = (end_time-start_time).total_seconds()
        total_nums = response["hits"]["total"]
        if (page%10) > 0:
            page_nums = int(total_nums/10) +1
        else:
            page_nums = int(total_nums/10)
        hit_list = []
        # for hit in response["hits"]["hits"]:
        #     hit_dict = {}
        #     if "title" in hit["highlight"]:
        #         hit_dict["title"] = "".join(hit["highlight"]["title"])
        #     else:
        #         hit_dict["title"] = hit["_source"]["title"]
        #     if "content" in hit["highlight"]:
        #         hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
        #     else:
        #         hit_dict["content"] = hit["_source"]["content"][:500]
        for hit in response["hits"]["hits"]:
            hit_dict = {}
            if "title" in hit["highlight"]:
                hit_dict["title"] = "".join(hit["highlight"]["title"])
            else:
                    hit_dict["title"] = hit["_source"]["title"]

            if "content" in hit["highlight"]:
                hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
                if site == "知乎":
                    hit_dict["content"] = BeautifulSoup(hit_dict["content"]).get_text()
            if site == "拉勾":
                if "job_desc" in hit["highlight"]:
                    hit_dict["content"] = "".join(hit["highlight"]["job_desc"])[:100]
            else:
                hit_dict["content"] = hit["_source"]["content"][:500]
                if site == "知乎":
                    hit_dict["content"] = BeautifulSoup(hit_dict["content"]).get_text()

            # if hit["_source"]["create_date"]:
            #     hit_dict["create_date"] = hit["_source"]["create_date"]
            # else:
            #     hit_dict["create_date"] = ""

            hit_dict["url"] = hit["_source"]["url"]
            hit_dict["score"] = hit["_score"]

            hit_list.append(hit_dict)



        return render(request, "result.html", {"page":page,
                                               "all_hits":hit_list,
                                               "key_words":key_words,
                                               "total_nums":total_nums,
                                               "page_nums":page_nums,
                                               "last_seconds":last_seconds,
                                               "jobbole_count":count,
                                               "topn_search":topn_search,
                                               "site": site,
                                               })

