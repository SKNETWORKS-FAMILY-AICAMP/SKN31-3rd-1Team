"""
modules.debug_qdrant

VectorDB(Qdrant)에서 검색이 안 되는 원인을 찾기 위한 진단 스크립트.

langchain 없이 qdrant_client로 직접 컬렉션 내용을 들여다봐서
"애초에 데이터가 잘 들어있는지" "payload 필드 이름이 뭔지"를 확인한다.

실행 방법 (프로젝트 루트에서):
    python -m modules.debug_qdrant
"""
import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv(override=True)

_QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "dementia_guides")


def main() -> None:
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # 1) 컬렉션 정보 확인 — 벡터 차원, 몇 개의 포인트(문서 조각)가 들어있는지
    info = client.get_collection(collection_name=_QDRANT_COLLECTION_NAME)
    print("=" * 50)
    print("1. 컬렉션 정보")
    print("=" * 50)
    print(f"저장된 포인트 개수: {info.points_count}")
    print(f"벡터 설정: {info.config.params.vectors}")
    print()

    if info.points_count == 0:
        print("⚠️  컬렉션에 데이터가 하나도 없습니다. 영선님이 적재를 아직 안 하셨거나,")
        print("    다른 컬렉션에 넣으셨을 가능성이 있습니다.")
        return

    # 2) 실제로 어떤 데이터가 들어있는지 샘플 3개만 꺼내본다.
    #    -> payload의 키 이름(page_content인지 text인지 content인지)을 확인하는 게 핵심.
    print("=" * 50)
    print("2. 저장된 데이터 샘플 (앞 3개)")
    print("=" * 50)
    points, _ = client.scroll(collection_name=_QDRANT_COLLECTION_NAME, limit=3, with_payload=True)
    for i, point in enumerate(points, 1):
        print(f"\n[샘플 {i}] id={point.id}")
        print(f"payload 키 목록: {list(point.payload.keys())}")
        # 내용이 너무 길면 앞부분만 보여준다.
        for key, value in point.payload.items():
            preview = str(value)[:200]
            print(f"  - {key}: {preview}")

    print()
    print("=" * 50)
    print("3. 확인 포인트")
    print("=" * 50)
    print(
        "langchain_qdrant.QdrantVectorStore 는 기본적으로 문서 내용이\n"
        "payload의 'page_content' 키에 들어있다고 가정합니다.\n"
        "위 payload 키 목록에 'page_content' 가 없다면 (예: 'text', 'content' 등),\n"
        "QdrantVectorStore 생성 시 content_payload_key 파라미터로 실제 키 이름을\n"
        "지정해줘야 검색 결과에서 내용을 제대로 읽어옵니다."
    )


if __name__ == "__main__":
    main()
